import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_fact_check_flow(async_client):
    r = await async_client.post("/api/fact-check", json={"question": "Is water wet?"})
    assert r.status_code == 200
    jid = r.json()["job_id"]

    import asyncio

    await asyncio.sleep(0.8)

    j = await async_client.get(f"/api/jobs/{jid}")
    assert j.status_code == 200
    body = j.json()
    assert body["status"] in ("completed", "running", "pending", "failed")


@pytest.mark.asyncio
async def test_job_cross_user_denied(monkeypatch):
    """Ensure another user's job id returns 403."""
    from httpx import ASGITransport, AsyncClient

    from app.db import async_session_factory
    from app.deps import get_current_user_id
    from app.main import app
    from app.models import Job

    async with async_session_factory() as session:
        job = Job(
            clerk_user_id="other_user",
            job_type="fact_check",
            status="completed",
            request_payload={"question": "x"},
            progress={},
            report_payload={"summary": "y"},
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        jid = job.id

    async def me():
        return "user_test_fixture"

    app.dependency_overrides[get_current_user_id] = me

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/jobs/{jid}")
        assert res.status_code == 403

    app.dependency_overrides.clear()
