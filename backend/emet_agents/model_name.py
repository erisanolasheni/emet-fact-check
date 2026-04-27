"""Chat model id for OpenAI-compatible APIs (OpenAI, OpenRouter, etc.)."""

import os


def resolved_chat_model() -> str:
    v = (os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    return v or "gpt-4o-mini"
