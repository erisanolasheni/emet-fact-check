import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from urllib.parse import urlparse

from agents import Runner

from emet_agents.evidence_sanitize import apply_allowed_urls, drop_forbidden_host_sources
from emet_agents.planner import WebSearchPlan, planner_agent
from emet_agents.result_schema import AgentFactItem, AgentSourceRef, FactCheckAgentResult
from emet_agents.runner_config import get_run_config
from emet_agents.search_factory import build_search_agent
from emet_agents.writer import writer_agent

EVIDENCE_PREAMBLE = """How this evidence was collected:
- **Ranked search:** Google Programmable Search is used when `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` are set in the server environment; otherwise DuckDuckGo text search (see `structured_research.py`).
- **Reading pages:** The top N URLs from that ranked list are fetched and main article text is extracted with `trafilatura` (see extract blocks below).

You MUST cite only URLs that appear under **URL (must be cited exactly for this source):** and align snippets with the extracted text for that URL.
---
"""

logger = logging.getLogger(__name__)


def _clamp_claim_support_to_verdict(result: FactCheckAgentResult) -> FactCheckAgentResult:
    if result.verdict != "refuted" or result.confidence_percent <= 40:
        return result
    return result.model_copy(update={"confidence_percent": min(result.confidence_percent, 35)})


def _host_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc or ""
    except Exception:
        return ""


async def run_fact_check(
    question: str,
    on_progress: Callable[[dict], Awaitable[None]],
    max_searches: int = 5,
) -> FactCheckAgentResult:
    from agents.mcp import MCPServerManager

    from app.config import settings
    from emet_agents.mcp_servers import build_mcp_servers

    async def emit(phase: str, message: str, percent: int | None = None, **extra: object) -> None:
        payload = {
            "phase": phase,
            "message": message,
            "percent": percent,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            payload.update(extra)
        await on_progress(payload)

    await emit("planning", "Planning targeted searches…", 10)

    run_config = get_run_config()
    plan_result = await Runner.run(
        planner_agent,
        f"Question to fact-check:\n{question}",
        run_config=run_config,
    )
    plan = plan_result.final_output_as(WebSearchPlan)
    searches = plan.searches[:max_searches]
    total_s = len(searches)

    steps_planned = [
        {"id": "plan", "label": "Plan searches", "status": "done"},
        {"id": "search", "label": "Gather sources", "status": "active"},
        {"id": "write", "label": "Synthesize verdict", "status": "pending"},
    ]
    await emit(
        "searching",
        f"Running {total_s} web searches…",
        25,
        steps=steps_planned,
    )

    mcp_candidates = build_mcp_servers(settings)
    allowed_urls: set[str] = set()
    used_structured = False

    async def run_one(idx: int, item, search_agent) -> str:
        inp = f"Search query: {item.query}\nReason: {item.reason}\nOriginal question: {question}"
        out = await Runner.run(search_agent, inp, run_config=run_config)
        pct = 25 + int(50 * (idx + 1) / max(total_s, 1))
        await emit(
            "searching",
            f"Search {idx + 1}/{total_s}: {item.query[:80]}…",
            min(pct, 75),
            steps=[
                {"id": "plan", "label": "Plan searches", "status": "done"},
                {"id": "search", "label": f"Gather sources ({idx + 1}/{total_s})", "status": "active"},
                {"id": "write", "label": "Synthesize verdict", "status": "pending"},
            ],
        )
        return str(out.final_output)

    async def gather_digests(search_agent) -> list[str]:
        if not searches:
            return []
        return await asyncio.gather(*[run_one(i, s, search_agent) for i, s in enumerate(searches)])

    digests: list[str] = []
    if mcp_candidates:
        async with MCPServerManager(
            mcp_candidates,
            strict=settings.emet_mcp_strict_connect,
            drop_failed_servers=True,
            connect_timeout_seconds=settings.emet_mcp_connect_timeout_seconds,
            cleanup_timeout_seconds=settings.emet_mcp_cleanup_timeout_seconds,
        ) as mgr:
            active = mgr.active_servers
            if active:
                logger.info("MCP search: %d server(s) connected", len(active))
                agent = build_search_agent(active)
            else:
                logger.warning(
                    "EMET_MCP_ENABLED but no MCP servers connected (%d failed); falling back to built-in search",
                    len(mgr.failed_servers),
                )
                agent = build_search_agent(None)
            digests = await gather_digests(agent)
    elif settings.emet_structured_research:
        from emet_agents.structured_research import build_structured_digests

        logger.info("Using structured research (ranked search + page extracts)")
        used_structured = True

        total_s = max(len(searches), 1)

        async def on_structured_step(completed: int, _total: int, query: str) -> None:
            pct = min(25 + int(50 * completed / total_s), 75)
            await emit(
                "searching",
                f"Structured research {completed}/{_total}: {query[:80]}…",
                pct,
                steps=[
                    {"id": "plan", "label": "Plan searches", "status": "done"},
                    {
                        "id": "search",
                        "label": f"Gather sources ({completed}/{_total})",
                        "status": "active",
                    },
                    {"id": "write", "label": "Synthesize verdict", "status": "pending"},
                ],
            )

        digests, allowed_urls = await build_structured_digests(
            searches, settings, on_step=on_structured_step
        )
    else:
        digests = await gather_digests(build_search_agent(None))

    await emit(
        "synthesizing",
        "Comparing sources and writing fact-check…",
        85,
        steps=[
            {"id": "plan", "label": "Plan searches", "status": "done"},
            {"id": "search", "label": "Gather sources", "status": "done"},
            {"id": "write", "label": "Synthesize verdict", "status": "active"},
        ],
    )

    preamble = EVIDENCE_PREAMBLE if used_structured else ""
    writer_input = (
        f"Original question:\n{question}\n\n{preamble}--- Evidence blocks ---\n"
        + "\n\n".join(f"Block {i+1}:\n{d}" for i, d in enumerate(digests))
    )

    writer_result = await Runner.run(writer_agent, writer_input, run_config=run_config)
    result = writer_result.final_output_as(FactCheckAgentResult)

    if used_structured and allowed_urls:
        result = apply_allowed_urls(result, allowed_urls)
    else:
        result = drop_forbidden_host_sources(result)

    result = _clamp_claim_support_to_verdict(result)

    for src in result.sources:
        if not src.hostname and src.url:
            src.hostname = _host_from_url(src.url)

    await emit(
        "finalizing",
        "Finalizing…",
        95,
        steps=[
            {"id": "plan", "label": "Plan searches", "status": "done"},
            {"id": "search", "label": "Gather sources", "status": "done"},
            {"id": "write", "label": "Synthesize verdict", "status": "done"},
        ],
    )

    return result


async def run_fact_check_mock(
    question: str,
    on_progress: Callable[[dict], Awaitable[None]],
) -> FactCheckAgentResult:
    async def emit(phase: str, message: str, percent: int | None = None) -> None:
        await on_progress(
            {
                "phase": phase,
                "message": message,
                "percent": percent,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    await emit("planning", "[mock] Planning…", 20)
    await asyncio.sleep(0.05)
    await emit("searching", "[mock] Searching…", 50)
    await asyncio.sleep(0.05)
    await emit("synthesizing", "[mock] Synthesizing…", 80)
    await asyncio.sleep(0.05)

    return FactCheckAgentResult(
        verdict="unclear",
        verdict_text="[Mock] No live verdict — enable API keys for a real result.",
        summary=f"[Mock] Verification outline for: {question[:120]}…",
        facts=[
            AgentFactItem(
                claim="Mock mode does not call live web search.",
                status="unknown",
                source_ids=["s1"],
                role="user_claim",
            )
        ],
        sources=[
            AgentSourceRef(
                id="s1",
                url="https://example.com",
                title="Example placeholder",
                snippet="Enable OPENAI_API_KEY for live fact-checking.",
                tier="other",
                hostname="example.com",
            )
        ],
        confidence_percent=10,
        confidence_rationale="Mock pipeline — no live evidence; claim support score is not meaningful here.",
        limitations=["Set OPENAI_API_KEY and disable EMET_MOCK_PIPELINE to use real searches."],
    )


def use_mock_pipeline() -> bool:
    return os.getenv("EMET_MOCK_PIPELINE", "").lower() in ("1", "true", "yes") or not os.getenv(
        "OPENAI_API_KEY", ""
    )
