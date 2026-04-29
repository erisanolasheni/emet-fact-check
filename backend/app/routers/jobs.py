import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import desc, select

from app.db import async_session_factory
from app.deps import get_current_user_id
from app.models import Job
from app.schemas import JobOut, JobPatchRequest

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_out(row: Job) -> JobOut:
    return JobOut(
        id=str(row.id),
        clerk_user_id=row.clerk_user_id,
        job_type=row.job_type,
        status=row.status,  # type: ignore[arg-type]
        progress=row.progress,
        report_payload=row.report_payload,
        request_payload=row.request_payload,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[JobOut])
async def list_jobs(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=100),
):
    async with async_session_factory() as session:
        q = await session.execute(
            select(Job)
            .where(Job.clerk_user_id == user_id)
            .order_by(desc(Job.created_at))
            .limit(limit)
        )
        rows = q.scalars().all()
        return [_job_out(r) for r in rows]


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
):
    async def event_generator():
        last_json = None
        try:
            while True:
                async with async_session_factory() as session:
                    job = await session.get(Job, job_id)
                    if not job:
                        yield f"event: error\ndata: {json.dumps({'detail': 'not_found'})}\n\n"
                        return
                    if job.clerk_user_id != user_id:
                        yield f"event: error\ndata: {json.dumps({'detail': 'forbidden'})}\n\n"
                        return

                    snapshot = {
                        "status": job.status,
                        "progress": job.progress,
                        "report_payload": job.report_payload if job.status == "completed" else None,
                        "error_message": job.error_message,
                    }
                    dumped = json.dumps(snapshot, default=str)
                    if dumped != last_json:
                        yield f"data: {dumped}\n\n"
                        last_json = dumped

                    if job.status in ("completed", "failed"):
                        yield f"event: terminal\ndata: {dumped}\n\n"
                        return

                await asyncio.sleep(0.7)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        if job.clerk_user_id != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
        return _job_out(job)


@router.patch("/{job_id}", response_model=JobOut)
async def patch_job(
    job_id: uuid.UUID,
    body: JobPatchRequest,
    user_id: str = Depends(get_current_user_id),
):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        if job.clerk_user_id != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
        payload = dict(job.request_payload or {})
        payload["display_title"] = body.display_title.strip()
        job.request_payload = payload
        await session.commit()
        await session.refresh(job)
        return _job_out(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
):
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        if job.clerk_user_id != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
        await session.delete(job)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
