"""Chat model id for OpenAI-compatible APIs (OpenAI, OpenRouter, etc.)."""

import os


def _strip_duplicate_openai_namespace(model: str) -> str:
    """OpenRouter expects ids like ``openai/gpt-4o``; ``openai/openai/...`` is invalid (400)."""
    m = model.strip()
    while m.startswith("openai/openai/"):
        m = m[6:]  # drop one redundant "openai/" prefix
    return m


def _from_pydantic_settings() -> str | None:
    """``LLM_MODEL`` in env and ``llm_model`` in Settings can diverge; prefer a single source of truth."""
    try:
        from app.config import settings

        v = (settings.llm_model or "").strip()
        return v or None
    except Exception:
        return None


def resolved_chat_model() -> str:
    return sync_llm_model_env()


def sync_llm_model_env() -> str:
    """Resolve LLM_MODEL from env + Settings, normalize for OpenRouter, set ``os.environ``."""
    v = (
        (os.getenv("LLM_MODEL") or "").strip()
        or (os.getenv("OPENAI_MODEL") or "").strip()
        or _from_pydantic_settings()
        or "gpt-4o-mini"
    )
    if not v:
        v = "gpt-4o-mini"
    out = _strip_duplicate_openai_namespace(v)
    os.environ["LLM_MODEL"] = out
    return out
