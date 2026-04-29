import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends

from app.config import settings
from app.db import async_session_factory
from app.deps import require_premium
from app.models import Job
from app.schemas import FactCheckEnqueueResponse, FactCheckRequest
from app.services.job_runner import enqueue_job, run_pipeline_for_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["fact-check"])


@router.post("/fact-check", response_model=FactCheckEnqueueResponse)
async def create_fact_check(
    body: FactCheckRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_premium),
):
    async with async_session_factory() as session:
        job = Job(
            clerk_user_id=user_id,
            job_type="fact_check",
            status="pending",
            request_payload={"question": body.question},
            progress={
                "phase": "queued",
                "message": "Queued…",
                "percent": 0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        jid = job.id

    sqs_dispatch = bool(settings.sqs_queue_url) and not settings.emet_run_pipeline_inline
    if sqs_dispatch:
        enqueue_job(job)

    run_inline = settings.use_background_worker and (
        not settings.sqs_queue_url or settings.emet_run_pipeline_inline
    )
    if run_inline:
        background_tasks.add_task(run_pipeline_for_job, jid)

    if not sqs_dispatch and not run_inline:
        logger.error(
            "Job %s: pipeline not scheduled — set USE_BACKGROUND_WORKER=true, or with "
            "SQS_QUEUE_URL set and no consumer set EMET_RUN_PIPELINE_INLINE=true for local runs.",
            jid,
        )
    elif sqs_dispatch:
        logger.info(
            "Job %s enqueued to SQS (in-process pipeline skipped). Local dev without a worker: "
            "EMET_RUN_PIPELINE_INLINE=true or unset SQS_QUEUE_URL.",
            jid,
        )

    return FactCheckEnqueueResponse(job_id=str(jid))
