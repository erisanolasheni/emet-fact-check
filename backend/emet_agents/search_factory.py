"""Fact-check search agent: OpenAI WebSearchTool, DuckDuckGo function tool, or MCP-derived tools."""

from __future__ import annotations

import os
from typing import Any

from agents import Agent, ModelSettings, WebSearchTool, function_tool

from emet_agents.ddg_web_search import run_ddg_web_search
from emet_agents.model_name import resolved_chat_model

INSTRUCTIONS_HOSTED = """You execute one web search and return a concise factual digest of results.

Include which domains appeared and note if sources agree. Do not speculate beyond snippets.
Stay under ~400 words.
"""

INSTRUCTIONS_DDG = """You must call the `emet_web_search` tool once with the given search query, then reply with a concise factual digest
of what the tool returned (domains, agreement across sources). Do not invent URLs or facts beyond the tool output.
Stay under ~400 words.
"""

INSTRUCTIONS_MCP = """You are the research step for a fact-checking pipeline. Use the MCP tools exposed by the server (search, fetch URL,
crawl, etc.—names depend on the server) to gather evidence for the user's search task.

Guidelines:
- Prefer authoritative sources when the tools expose URLs or snippets.
- Call tools as needed (you may chain calls), then produce one plain-text digest under ~500 words.
- End with a short "Domains seen:" line listing key hostnames if the tools returned URLs.
- If a tool errors, note it briefly and continue with what you have.
"""


def _third_party_llm_base() -> bool:
    """OpenAI-hosted WebSearchTool is not supported on OpenRouter / most OpenAI-compatible gateways."""
    return bool((os.getenv("LLM_BASE_URL") or "").strip())


@function_tool
async def emet_web_search(query: str) -> str:
    """Search the public web (DuckDuckGo). Pass one focused query; returns titles, snippets, and URLs."""
    return await run_ddg_web_search(query)


def build_search_agent(mcp_servers: list[Any] | None) -> Agent:
    """Create the search agent for one parallel fact-check slice.

    Args:
        mcp_servers: Connected MCP servers from ``MCPServerManager.active_servers``, or ``None``
            to use built-in web search (OpenAI hosted or DuckDuckGo fallback).
    """
    servers = mcp_servers or []
    if servers:
        return Agent(
            name="FactCheckSearch",
            instructions=INSTRUCTIONS_MCP,
            tools=[],
            mcp_servers=list(servers),
            mcp_config={"convert_schemas_to_strict": False},
            model=resolved_chat_model(),
            model_settings=ModelSettings(tool_choice="auto"),
        )
    if _third_party_llm_base():
        return Agent(
            name="FactCheckSearch",
            instructions=INSTRUCTIONS_DDG,
            tools=[emet_web_search],
            model=resolved_chat_model(),
            model_settings=ModelSettings(tool_choice="required"),
        )
    return Agent(
        name="FactCheckSearch",
        instructions=INSTRUCTIONS_HOSTED,
        tools=[WebSearchTool(search_context_size="low")],
        model=resolved_chat_model(),
        model_settings=ModelSettings(tool_choice="required"),
    )
