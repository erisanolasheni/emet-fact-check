from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Loads repo-root `.env` (see `.env.example`).
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-backed settings. See `.env.example`."""

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
    llm_base_url: str = ""
    llm_model: str = "gpt-4o-mini"

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

    google_api_key: str = ""
    google_cse_id: str = ""

    emet_structured_research: bool = True
    emet_research_top_urls: int = 5
    emet_page_excerpt_max_chars: int = 6000
    emet_fetch_concurrency: int = 4

    sqs_queue_url: str = ""
    aws_region: str = "us-east-1"
    use_background_worker: bool = True
    emet_run_pipeline_inline: bool = True

    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001"
    )


settings = Settings()
