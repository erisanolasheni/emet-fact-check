import json
import logging
import uuid
from datetime import datetime, timezone

import boto3
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session_factory
from app.models import Job
from app.schemas import FactCheckResult
from emet_agents.pipeline import run_fact_check, run_fact_check_mock, use_mock_pipeline

logger = logging.getLogger(__name__)


def _sqs_send(job_id: str, clerk_user_id: str) -> None:
    if not settings.sqs_queue_url:
        return
    client = boto3.client("sqs", region_name=settings.aws_region)
    client.send_message(
        QueueUrl=settings.sqs_queue_url,
        MessageBody=json.dumps({"job_id": job_id, "clerk_user_id": clerk_user_id}),
    )
    logger.info("Sent job %s to SQS", job_id)


async def _persist_progress(session: AsyncSession, job_id: uuid.UUID, payload: dict) -> None:
    payload = {**payload, "updated_at": datetime.now(timezone.utc).isoformat()}
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(progress=payload, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def run_pipeline_for_job(job_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            logger.error("Job %s not found", job_id)
            return

        question = job.request_payload.get("question", "")

        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status="running", updated_at=datetime.now(timezone.utc))
        )
        await session.commit()

    async def on_progress(p: dict) -> None:
        async with async_session_factory() as s2:
            await _persist_progress(s2, job_id, p)

    try:
        if use_mock_pipeline():
            agent_result = await run_fact_check_mock(question, on_progress)
        else:
            agent_result = await run_fact_check(question, on_progress)

        report = FactCheckResult.model_validate(agent_result.model_dump())

        async with async_session_factory() as session:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="completed",
                    report_payload=report.model_dump(),
                    progress={
                        "phase": "finalizing",
                        "message": "Complete",
                        "percent": 100,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
        logger.info("Job %s completed", job_id)
    except Exception as e:
        logger.exception("Job %s failed: %s", job_id, e)
        async with async_session_factory() as session:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="failed",
                    error_message=str(e)[:2000],
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()


def enqueue_job(job: Job) -> None:
    """Notify external worker via SQS."""
    _sqs_send(str(job.id), job.clerk_user_id)


async def fetch_job_for_user(job_id: uuid.UUID, clerk_user_id: str) -> Job | None:
    async with async_session_factory() as session:
        q = await session.execute(select(Job).where(Job.id == job_id))
        row = q.scalar_one_or_none()
        if row and row.clerk_user_id != clerk_user_id:
            return None
        return row
