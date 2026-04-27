import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./emet_test.db")
os.environ.setdefault("CLERK_JWKS_URL", "https://example.invalid/.well-known/jwks.json")
os.environ.setdefault("EMET_MOCK_PIPELINE", "true")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("REQUIRE_SUBSCRIPTION", "false")
# Repo-root .env may contain OpenRouter keys; agents tracing otherwise POSTs to api.openai.com.
os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "true")

from app.deps import get_current_user_id  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
async def prepare_db():
    from app.db import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def async_client():
    async def fake_user():
        return "user_test_fixture"

    app.dependency_overrides[get_current_user_id] = fake_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def clerk_client(async_client):  # noqa: ARG001
    return async_client
