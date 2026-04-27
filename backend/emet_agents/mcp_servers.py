"""Build MCP server instances from application settings (stdio / SSE / streamable HTTP)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


def _parse_json_object(raw: str, label: str) -> dict[str, str] | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        val = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("%s: invalid JSON (%s)", label, e)
        return None
    if isinstance(val, dict):
        out: dict[str, str] = {}
        for k, v in val.items():
            if v is not None and v is not ...:
                out[str(k)] = str(v)
        return out
    logger.warning("%s: expected JSON object, got %s", label, type(val).__name__)
    return None


def _parse_json_array(raw: str, label: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        val = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("%s: invalid JSON (%s)", label, e)
        return []
    if isinstance(val, list):
        return [str(x) for x in val if x is not None]
    logger.warning("%s: expected JSON array, got %s", label, type(val).__name__)
    return []


def _tool_filter_from_settings(settings: Settings) -> Any:
    allow = [s.strip() for s in (settings.emet_mcp_tool_allowlist or "").split(",") if s.strip()]
    if not allow:
        return None
    try:
        from agents.mcp import create_static_tool_filter

        return create_static_tool_filter(allowed_tool_names=allow)
    except Exception as e:  # pragma: no cover
        logger.warning("Could not build MCP tool allowlist filter: %s", e)
        return None


def build_mcp_servers(settings: Settings) -> list[Any]:
    """Return a list of MCPServer instances (not yet connected). Empty if MCP disabled or misconfigured."""
    if not settings.emet_mcp_enabled:
        return []

    try:
        from agents.mcp import MCPServerSse, MCPServerStdio, MCPServerStreamableHttp
    except ImportError as e:
        logger.error("agents.mcp is unavailable (install openai-agents with MCP extras): %s", e)
        return []

    transport = (settings.emet_mcp_transport or "").strip().lower()
    tool_filter = _tool_filter_from_settings(settings)
    name = (settings.emet_mcp_server_name or "").strip() or None
    cache_tools = True

    if transport == "stdio":
        cmd = (settings.emet_mcp_stdio_command or "").strip()
        if not cmd:
            logger.warning("EMET_MCP_ENABLED but EMET_MCP_STDIO_COMMAND is empty")
            return []
        args = _parse_json_array(settings.emet_mcp_stdio_args_json, "EMET_MCP_STDIO_ARGS_JSON")
        env_merged = _parse_json_object(settings.emet_mcp_stdio_env_json, "EMET_MCP_STDIO_ENV_JSON")
        params: dict[str, Any] = {"command": cmd, "args": args}
        if env_merged:
            params["env"] = env_merged
        server = MCPServerStdio(
            params,  # type: ignore[arg-type]
            cache_tools_list=cache_tools,
            name=name,
            tool_filter=tool_filter,
        )
        return [server]

    if transport in ("sse", "streamable_http", "streamable-http"):
        url = (settings.emet_mcp_url or "").strip()
        if not url:
            logger.warning("EMET_MCP_TRANSPORT=%s but EMET_MCP_URL is empty", transport)
            return []
        headers = _parse_json_object(settings.emet_mcp_headers_json, "EMET_MCP_HEADERS_JSON") or {}

        if transport == "sse":
            params = {"url": url}
            if headers:
                params["headers"] = headers
            server = MCPServerSse(params, cache_tools_list=cache_tools, name=name, tool_filter=tool_filter)
        else:
            params = {"url": url}
            if headers:
                params["headers"] = headers
            params["ignore_initialized_notification_failure"] = True
            server = MCPServerStreamableHttp(
                params,  # type: ignore[arg-type]
                cache_tools_list=cache_tools,
                name=name,
                tool_filter=tool_filter,
            )
        return [server]

    if transport:
        logger.warning("Unknown EMET_MCP_TRANSPORT=%r (use stdio, sse, or streamable_http)", transport)
    else:
        logger.warning("EMET_MCP_ENABLED but EMET_MCP_TRANSPORT is empty")
    return []
