from typing import Literal

from pydantic import BaseModel, Field


class AgentSourceRef(BaseModel):
    id: str = Field(description="Stable id like s1, s2")
    url: str
    title: str
    snippet: str = ""
    tier: str = "secondary"
    hostname: str = ""
    published_at: str | None = None


class AgentFactItem(BaseModel):
    claim: str
    status: Literal["supported", "partially_supported", "contradicted", "unknown"]
    source_ids: list[str] = Field(default_factory=list)
    role: Literal["user_claim", "evidence"] | None = Field(
        default=None,
        description="user_claim: headline; evidence: supporting detail. Omit for legacy payloads.",
    )


class FactCheckAgentResult(BaseModel):
    verdict: Literal["supported", "refuted", "partial", "unclear"] = Field(
        default="unclear",
        description="Judgment on the user's main claim.",
    )
    verdict_text: str = Field(
        default="",
        description="One-line headline, e.g. Not supported: … or Supported: …",
    )
    summary: str
    facts: list[AgentFactItem]
    sources: list[AgentSourceRef]
    confidence_percent: int = Field(
        ge=0,
        le=100,
        description="Support for the user's specific claim (not generic research quality).",
    )
    confidence_rationale: str
    limitations: list[str] = Field(default_factory=list)
