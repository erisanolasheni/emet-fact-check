"""
Ranked web search (Google CSE or DuckDuckGo) + main-text excerpts from top result pages.

Replaces "agent guesses a digest" for the default / OpenRouter path so citations map to
real URLs and on-page text the model can quote or paraphrase.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

# Skip non-HTTP(S) and obvious junk
_BORING = frozenset(
    {
        "example.com",
        "www.example.com",
        "example.org",
        "www.example.org",
    }
)


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _is_fetchable(url: str) -> bool:
    u = (url or "").strip()
    if not u.startswith(("http://", "https://")):
        return False
    h = _hostname(u)
    if h in _BORING or h.endswith("example.com") or h.endswith("example.org"):
        return False
    return True


async def _google_cse_hits(query: str, settings: Settings) -> list[dict[str, str]]:
    if not (settings.google_api_key and settings.google_cse_id):
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": settings.google_api_key,
        "cx": settings.google_cse_id,
        "q": query,
        "num": 10,
    }
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(url, params=params)
    except Exception as exc:
        logger.warning("Google CSE request failed: %s", exc)
        return []
    if r.status_code != 200:
        logger.warning("Google CSE HTTP %s: %s", r.status_code, (r.text or "")[:300])
        return []
    try:
        data = r.json()
    except Exception:
        return []
    out: list[dict[str, str]] = []
    for it in data.get("items") or []:
        link = (it.get("link") or "").strip()
        if not link or not _is_fetchable(link):
            continue
        out.append(
            {
                "title": (it.get("title") or "").strip() or link,
                "url": link,
                "snippet": (it.get("snippet") or "").strip(),
            }
        )
    return out


def _ddg_hits_sync(query: str, max_results: int) -> list[dict[str, str]]:
    """Ranked text results via the `ddgs` package (DuckDuckGo / multi-engine)."""
    from ddgs import DDGS

    out: list[dict[str, str]] = []
    try:
        with DDGS() as d:
            raw = list(d.text(query, max_results=max_results))
    except Exception as exc:  # pragma: no cover - network / rate limits
        logger.warning("ddgs text search failed for %r: %s", query[:120], exc)
        return out
    for r in raw:
        href = (r.get("href") or r.get("url") or "").strip()
        if not href or not _is_fetchable(href):
            continue
        body = (r.get("body") or "") or ""
        out.append(
            {
                "title": (r.get("title") or "").strip() or href,
                "url": href,
                "snippet": body[:800].strip(),
            }
        )
    if not out:
        logger.warning("ddgs returned no fetchable URLs for query %r", query[:120])
    return out


async def ranked_search_hits(query: str, settings: Settings, max_results: int = 8) -> list[dict[str, str]]:
    """Return ranked {title, url, snippet} from Google CSE if configured, else DDG text API."""
    g = await _google_cse_hits(query, settings)
    if g:
        return g[:max_results]
    return await asyncio.to_thread(_ddg_hits_sync, query, max_results)


def _fetch_page_excerpt_sync(url: str, max_chars: int) -> str:
    try:
        import trafilatura
    except ImportError:
        return "[trafilatura not installed]"

    from trafilatura import extract

    try:
        html = trafilatura.fetch_url(url)
        if not html:
            return ""
        text = extract(html, url=url, include_comments=False, include_tables=False) or ""
        text = " ".join(text.split())
        return text[:max_chars] if text else ""
    except Exception as exc:  # pragma: no cover
        logger.debug("trafilatura extract failed for %s: %s", url, exc)
        return ""


async def _fetch_excerpt(url: str, max_chars: int) -> str:
    return await asyncio.to_thread(_fetch_page_excerpt_sync, url, max_chars)


async def build_evidence_digest_for_query(
    query: str,
    reason: str,
    index: int,
    settings: Settings,
) -> tuple[str, set[str]]:
    """
    One search line from the plan → ranked results → fetch top pages → one markdown digest.
    Returns (digest, allowed_url_set for citation grounding).
    """
    hits = await ranked_search_hits(query, settings, max_results=max(10, settings.emet_research_top_urls + 2))
    top_n = settings.emet_research_top_urls
    hits = hits[:top_n]

    lines: list[str] = [
        f"## Search {index + 1}: {query!r}",
        f"**Angle / reason (from planner):** {reason}",
        "",
    ]
    if not hits:
        lines.append(
            "*No ranked results (Google CSE and DuckDuckGo both empty or errored). "
            "Do not invent URLs. Note this in limitations.*"
        )
        return "\n".join(lines), set()

    allowed: set[str] = {h["url"] for h in hits}
    max_chars = settings.emet_page_excerpt_max_chars
    sem = asyncio.Semaphore(max(1, settings.emet_fetch_concurrency))

    async def one(i: int, hit: dict[str, str]) -> str:
        url = hit["url"]
        title = hit["title"]
        snip = hit["snippet"]
        async with sem:
            body = await _fetch_excerpt(url, max_chars) if _is_fetchable(url) else ""
        if not body:
            body = "*Could not extract main article text; rely on the search snippet only.*"
        return (
            f"### Result {i + 1}\n"
            f"- **URL (must be cited exactly for this source):** {url}\n"
            f"- **Title:** {title}\n"
            f"- **Search snippet:** {snip}\n"
            f"- **Extracted on-page text (excerpt):**\n\n{body}\n"
        )

    blocks = await asyncio.gather(*[one(i, h) for i, h in enumerate(hits)])
    lines.append("\n\n".join(blocks))
    return "\n".join(lines), allowed


async def build_structured_digests(
    plan_items: list[Any],
    settings: Settings,
    on_step: Callable[[int, int, str], Awaitable[None]] | None = None,
) -> tuple[list[str], set[str]]:
    """
    For each WebSearchItem, run ranked search + page fetches, return per-step digests
    and the union of URLs that the writer is allowed to cite. Queries run in parallel.

    ``on_step(completed, total, query)`` is awaited after each parallel unit finishes, so
    the UI can update percent while work is in flight (unbounded gather with no progress).
    """
    if not plan_items:
        return [], set()

    total = len(plan_items)

    async def one(i: int, item: Any) -> tuple[int, str, set[str], Any]:
        q = getattr(item, "query", "") or ""
        rsn = getattr(item, "reason", "") or ""
        text, allow = await build_evidence_digest_for_query(q, rsn, i, settings)
        return i, text, allow, item

    cors = [one(i, item) for i, item in enumerate(plan_items)]
    acc: list[tuple[int, str, set[str]]] = []
    done = 0
    for completed in asyncio.as_completed(cors):
        i, text, allow, item = await completed
        acc.append((i, text, allow))
        done += 1
        if on_step:
            q = getattr(item, "query", "") or ""
            await on_step(done, total, q)

    acc.sort(key=lambda x: x[0])
    digests = [a[1] for a in acc]
    all_allowed: set[str] = set()
    for a in acc:
        all_allowed |= a[2]
    return digests, all_allowed
