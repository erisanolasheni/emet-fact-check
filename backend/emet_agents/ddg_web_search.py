"""DuckDuckGo Instant Answer API — plain HTTP, no OpenAI-hosted tools (OpenRouter–compatible)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DDG_URL = "https://api.duckduckgo.com/"
_MAX_TOPICS = 12
_UA = "EmetFactCheck/1.0"


def _flatten_topics(item: Any, out: list[tuple[str, str]], limit: int) -> None:
    if len(out) >= limit or not isinstance(item, dict):
        return
    nested = item.get("Topics")
    if isinstance(nested, list):
        for sub in nested:
            _flatten_topics(sub, out, limit)
        return
    text = (item.get("Text") or "").strip()
    url = (item.get("FirstURL") or "").strip()
    if text or url:
        out.append((text, url))


async def run_ddg_web_search(query: str) -> str:
    """Return a text digest (snippets + URLs) for the model."""
    q = (query or "").strip()
    if not q:
        return "Empty query; provide a non-empty search string."

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": _UA, "Accept": "application/json"},
        ) as client:
            r = await client.get(
                _DDG_URL,
                params={"q": q, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)
        return f"Web search failed ({exc!s}). Proceed with low confidence and note the gap in limitations."

    lines: list[str] = []

    abst = (data.get("AbstractText") or "").strip()
    if abst:
        heading = (data.get("Heading") or "").strip()
        src = (data.get("AbstractSource") or "").strip()
        aurl = (data.get("AbstractURL") or "").strip()
        block = f"Summary: {abst}"
        if heading:
            block = f"{heading} — {block}"
        if aurl:
            block += f"\nURL: {aurl}"
        if src:
            block += f"\nSource label: {src}"
        lines.append(block)

    ans = (data.get("Answer") or "").strip()
    if ans:
        lines.append(f"Instant answer: {ans}")

    for row in (data.get("Results") or [])[:_MAX_TOPICS]:
        if not isinstance(row, dict):
            continue
        t = (row.get("Text") or "").strip()
        u = (row.get("FirstURL") or "").strip()
        if t or u:
            lines.append(f"- {t} ({u})".strip())

    topics: list[tuple[str, str]] = []
    for item in data.get("RelatedTopics") or []:
        _flatten_topics(item, topics, _MAX_TOPICS)
    for t, u in topics[:_MAX_TOPICS]:
        lines.append(f"- {t} ({u})".strip())

    if not lines:
        return (
            "No structured hits from DuckDuckGo for this query. "
            "Note limited web evidence in your digest and suggest follow-up queries."
        )

    return f"DuckDuckGo results for {q!r}:\n" + "\n".join(lines)
