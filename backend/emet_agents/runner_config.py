from __future__ import annotations

from agents.models.multi_provider import MultiProvider
from agents.run_config import RunConfig

from app.config import settings


def get_run_config() -> RunConfig:
    base = (settings.llm_base_url or "").strip().rstrip("/")
    if not base:
        return RunConfig()
    return RunConfig(
        model_provider=MultiProvider(
            openai_api_key=settings.openai_api_key or None,
            openai_base_url=base,
            openai_use_responses=False,
            openai_prefix_mode="model_id",
            unknown_prefix_mode="model_id",
        )
    )
