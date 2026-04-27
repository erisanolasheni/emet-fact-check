"""Restrict writer output to evidence-backed URLs; strip placeholders like example.com."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from emet_agents.result_schema import AgentFactItem, AgentSourceRef, FactCheckAgentResult

_URL_RE = re.compile(r"https?://[^\s)>\]\"'<>]+", re.IGNORECASE)

_BAD_HOSTS = frozenset(
    {
        "example.com",
        "www.example.com",
        "example.org",
        "www.example.org",
    }
)


def extract_urls_from_text(text: str) -> set[str]:
    return {m.rstrip(").,;") for m in _URL_RE.findall(text or "")}


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _bad_host(h: str) -> bool:
    h = h.lower()
    if h in _BAD_HOSTS:
        return True
    for b in _BAD_HOSTS:
        if h == b or h.endswith("." + b):
            return True
    return False


def _norm(url: str) -> str:
    u = (url or "").strip().split("#", 1)[0].rstrip("/")
    return u


def _url_allowed(cited: str, allowed: set[str]) -> str | None:
    """If cited URL is grounded in *allowed* (exact or one is prefix of the other), return chosen canonical from allowed."""
    c = _norm(cited)
    if not c:
        return None
    for a in allowed:
        if not a or _bad_host(_host(a)):
            continue
        an = _norm(a)
        if c == an or c.startswith(an + "/") or an.startswith(c + "/") or c == an:
            return a
    return None


def apply_allowed_urls(
    result: FactCheckAgentResult,
    allowed_urls: set[str],
) -> FactCheckAgentResult:
    """Keep only sources that cite URLs present in the evidence; remap fact source_ids. Drop example.com, etc."""
    if not allowed_urls:
        return result
    # Only keep allowed targets that are safe
    clean_allow = {u for u in allowed_urls if u and not _bad_host(_host(u))}
    if not clean_allow:
        return result

    id_old_to_new: dict[str, str] = {}
    kept: list[AgentSourceRef] = []
    n = 0
    for s in result.sources:
        canon = _url_allowed(s.url, clean_allow)
        if not canon:
            continue
        n += 1
        nid = f"s{n}"
        id_old_to_new[s.id] = nid
        h = _host(canon)
        kept.append(
            AgentSourceRef(
                id=nid,
                url=canon,
                title=s.title,
                snippet=s.snippet,
                tier=s.tier,
                hostname=h,
                published_at=s.published_at,
            )
        )
    if not kept:
        # Do not return ungrounded model output; evidence existed but was not cited.
        return FactCheckAgentResult(
            verdict=result.verdict,
            verdict_text=result.verdict_text,
            summary=result.summary,
            facts=[
                AgentFactItem(
                    claim=f.claim,
                    status="unknown" if f.status in ("supported", "partially_supported") else f.status,
                    source_ids=[],
                    role=f.role,
                )
                for f in result.facts
            ],
            sources=[],
            confidence_percent=max(0, result.confidence_percent - 20),
            confidence_rationale=result.confidence_rationale
            + " (No source URLs matched the ranked-search evidence set; citations were not grounded.)",
            limitations=result.limitations
            + [
                "The model did not cite any URL from the retrieved evidence. "
                "Re-run or check that the writer is restricted to the listed evidence URLs only."
            ],
        )

    new_facts: list[AgentFactItem] = []
    for f in result.facts:
        new_ids = [id_old_to_new[i] for i in (f.source_ids or []) if i in id_old_to_new]
        st = f.status
        if not new_ids and f.source_ids and st in ("supported", "partially_supported"):
            st = "unknown"
        new_facts.append(AgentFactItem(claim=f.claim, status=st, source_ids=new_ids, role=f.role))

    extra = []
    if len(kept) < len(result.sources):
        extra.append("Citations were filtered to evidence URLs from ranked search and page fetches only.")

    return FactCheckAgentResult(
        verdict=result.verdict,
        verdict_text=result.verdict_text,
        summary=result.summary,
        facts=new_facts,
        sources=kept,
        confidence_percent=result.confidence_percent,
        confidence_rationale=result.confidence_rationale,
        limitations=result.limitations + extra,
    )


def drop_forbidden_host_sources(result: FactCheckAgentResult) -> FactCheckAgentResult:
    """Remove example.com and similar placeholders when not using URL allowlists (MCP/legacy path)."""
    id_old_to_new: dict[str, str] = {}
    kept: list[AgentSourceRef] = []
    n = 0
    for s in result.sources:
        if _bad_host(_host(s.url or "")):
            continue
        n += 1
        nid = f"s{n}"
        id_old_to_new[s.id] = nid
        u = s.url
        kept.append(
            AgentSourceRef(
                id=nid,
                url=u,
                title=s.title,
                snippet=s.snippet,
                tier=s.tier,
                hostname=_host(u),
                published_at=s.published_at,
            )
        )
    if len(kept) == len(result.sources):
        return result
    new_facts: list[AgentFactItem] = []
    for f in result.facts:
        new_ids = [id_old_to_new[i] for i in (f.source_ids or []) if i in id_old_to_new]
        st = f.status
        if f.source_ids and not new_ids and st in ("supported", "partially_supported"):
            st = "unknown"
        new_facts.append(AgentFactItem(claim=f.claim, status=st, source_ids=new_ids, role=f.role))
    return FactCheckAgentResult(
        verdict=result.verdict,
        verdict_text=result.verdict_text,
        summary=result.summary,
        facts=new_facts,
        sources=kept,
        confidence_percent=result.confidence_percent,
        confidence_rationale=result.confidence_rationale,
        limitations=result.limitations
        + (["Removed placeholder or invalid URLs from the model output."] if n < len(result.sources) else []),
    )
