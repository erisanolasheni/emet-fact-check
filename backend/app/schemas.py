from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

JobStatus = Literal["pending", "running", "completed", "failed"]


class FactCheckRequest(BaseModel):
    question: str = Field(max_length=8000)

    @field_validator("question")
    @classmethod
    def validate_question_len(cls, value: str) -> str:
        text = value.strip()
        if len(text) < 3:
            raise ValueError("Enter at least 3 characters.")
        return text


class JobPatchRequest(BaseModel):
    """Sidebar display name; stored in `request_payload.display_title`."""

    display_title: str = Field(min_length=1, max_length=200)


class SourceRef(BaseModel):
    id: str
    url: str
    title: str
    snippet: str = ""
    tier: str = "secondary"
    hostname: str = ""
    published_at: str | None = None


class FactItem(BaseModel):
    claim: str
    status: Literal["supported", "partially_supported", "contradicted", "unknown"]
    source_ids: list[str] = Field(default_factory=list)
    role: Literal["user_claim", "evidence"] | None = None


class FactCheckResult(BaseModel):
    verdict: Literal["supported", "refuted", "partial", "unclear"] = "unclear"
    verdict_text: str = ""
    summary: str
    facts: list[FactItem]
    sources: list[SourceRef]
    confidence_percent: int = Field(ge=0, le=100)
    confidence_rationale: str
    limitations: list[str] = Field(default_factory=list)


class JobProgressDTO(BaseModel):
    phase: str
    message: str
    percent: int | None = None
    steps: list[dict[str, Any]] | None = None
    updated_at: str | None = None


class JobOut(BaseModel):
    id: str
    clerk_user_id: str
    job_type: str
    status: JobStatus
    progress: JobProgressDTO | dict | None
    report_payload: FactCheckResult | dict | None
    request_payload: dict
    error_message: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class FactCheckEnqueueResponse(BaseModel):
    job_id: str
    message: str = "Fact-check started."


class SubscriptionStatusOut(BaseModel):
    has_premium: bool
