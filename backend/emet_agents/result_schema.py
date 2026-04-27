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
    # user_claim = headline claim; evidence = neutral "from sources" (omit/null = older reports — UI falls back to status colors)
    role: Literal["user_claim", "evidence"] | None = None


class FactCheckAgentResult(BaseModel):
    # Whether the *user’s main* claim is supported, before narrative summary
    verdict: Literal["supported", "refuted", "partial", "unclear"] = "unclear"
    verdict_text: str = Field(
        default="",
        description="One-line headline, e.g. Not supported: … or Supported: …",
    )
    summary: str
    facts: list[AgentFactItem]
    sources: list[AgentSourceRef]
    # How well the *user’s specific claim* is supported (NOT generic research quality). Low when refuted.
    confidence_percent: int = Field(ge=0, le=100)
    confidence_rationale: str
    limitations: list[str] = Field(default_factory=list)
