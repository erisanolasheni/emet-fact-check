from app.config import Settings


def test_build_mcp_servers_disabled_by_default():
    s = Settings(
        emet_mcp_enabled=False,
    )
    from emet_agents.mcp_servers import build_mcp_servers

    assert build_mcp_servers(s) == []


def test_build_mcp_stdio_requires_command():
    s = Settings(
        emet_mcp_enabled=True,
        emet_mcp_transport="stdio",
        emet_mcp_stdio_command="",
    )
    from emet_agents.mcp_servers import build_mcp_servers

    assert build_mcp_servers(s) == []
