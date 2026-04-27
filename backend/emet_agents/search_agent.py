"""Search agent for fact-checking — prefer ``build_search_agent`` from ``search_factory`` (used by ``pipeline``)."""

from emet_agents.search_factory import build_search_agent, emet_web_search

# Default agent without MCP (OpenAI WebSearch or DuckDuckGo depending on LLM_BASE_URL).
search_agent = build_search_agent(None)

__all__ = ["build_search_agent", "emet_web_search", "search_agent"]
