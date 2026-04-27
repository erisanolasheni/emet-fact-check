from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Single backend env file: repository root `emet/.env` (see `.env.example`).
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://emet:emet@localhost:5432/emet"
    clerk_jwks_url: str = ""
    clerk_secret_key: str = ""
    clerk_premium_plan_key: str = "emet_subscription"
    require_subscription: bool = False
    openai_api_key: str = ""
    # OpenAI-compatible HTTP API (OpenRouter, Azure OpenAI, local proxies). Empty = official api.openai.com.
    llm_base_url: str = ""
    # Model id for that API (e.g. OpenRouter: openai/gpt-4o-mini). Also read at agent import via LLM_MODEL env.
    llm_model: str = "gpt-4o-mini"

    # --- MCP (Model Context Protocol) for search / research tools ---
    # When enabled and transport is valid, the fact-check pipeline wraps search in MCPServerManager
    # and attaches tools from your MCP server(s). See README "MCP integration".
    emet_mcp_enabled: bool = False
    emet_mcp_transport: str = ""  # stdio | sse | streamable_http
    emet_mcp_url: str = ""
    emet_mcp_stdio_command: str = ""
    emet_mcp_stdio_args_json: str = "[]"
    emet_mcp_stdio_env_json: str = ""
    emet_mcp_headers_json: str = ""
    emet_mcp_tool_allowlist: str = ""
    emet_mcp_server_name: str | None = None
    emet_mcp_strict_connect: bool = False
    emet_mcp_connect_timeout_seconds: float = 30.0
    emet_mcp_cleanup_timeout_seconds: float = 20.0

    # Google Programmable Search (optional) — “search then read top results” for grounded citations
    # Create a CSE: https://programmablesearchengine.google.com/ and get JSON API key in Cloud Console
    google_api_key: str = ""
    google_cse_id: str = ""

    # Ranked search + trafilatura page text for default pipeline (no MCP). Set false to use the legacy LLM+tool digest only.
    emet_structured_research: bool = True
    emet_research_top_urls: int = 5
    emet_page_excerpt_max_chars: int = 6000
    emet_fetch_concurrency: int = 4

    sqs_queue_url: str = ""
    aws_region: str = "us-east-1"
    use_background_worker: bool = True
    #: When True (default), run the pipeline in this API process (BackgroundTasks). Set False with
    #: ``SQS_QUEUE_URL`` when a dedicated SQS/Lambda worker should be the only runner (production).
    emet_run_pipeline_inline: bool = True

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


settings = Settings()
