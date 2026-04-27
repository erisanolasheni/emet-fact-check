"""
Optional SQS consumer — run separate from API when SQS_QUEUE_URL is set.

Example: AWS_LAMBDA or EC2/systemd invoking this loop, or `python worker_sqs.py`.
"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

import boto3
from dotenv import load_dotenv

from app.services.job_runner import run_pipeline_for_job

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def poll_loop() -> None:
    queue_url = os.getenv("SQS_QUEUE_URL")
    region = os.getenv("AWS_REGION", "us-east-1")
    if not queue_url:
        logger.error("SQS_QUEUE_URL not set")
        return

    client = boto3.client("sqs", region_name=region)

    logger.info("Polling %s …", queue_url)

    while True:
        resp = client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=900,
        )
        for msg in resp.get("Messages", []):
            body = json.loads(msg["Body"])
            job_id = uuid.UUID(body["job_id"])
            await run_pipeline_for_job(job_id)
            client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=msg["ReceiptHandle"],
            )
            logger.info("Processed job %s", job_id)
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(poll_loop())
