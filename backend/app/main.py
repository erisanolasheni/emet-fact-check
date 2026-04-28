import os
from contextlib import asynccontextmanager
from pathlib import Path

from agents import set_default_openai_client
from agents.models._openai_shared import set_use_responses_by_default
from dotenv import load_dotenv
from openai import AsyncOpenAI

_repo_root = Path(__file__).resolve().parents[2]
load_dotenv(_repo_root / ".env", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, engine
from app.routers import factcheck
from app.routers import jobs as jobs_router
from app.routers import subscription as subscription_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    base = (settings.llm_base_url or "").strip().rstrip("/")
    if base and settings.openai_api_key:
        # OpenAI-compatible base URL: use chat completions, not the Responses API.
        os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"
        set_use_responses_by_default(False)
        set_default_openai_client(
            AsyncOpenAI(api_key=settings.openai_api_key, base_url=base),
            use_for_tracing=False,
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Emet API",
    description="Fact-checking with evidence and confidence",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(jobs_router.router)
app.include_router(factcheck.router)
app.include_router(subscription_router.router)
