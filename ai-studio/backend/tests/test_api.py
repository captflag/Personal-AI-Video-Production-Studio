"""
tests/test_api.py
-----------------
Endpoint-level tests for the AI Studio FastAPI gateway.
These use httpx's AsyncClient and mock out the ARQ pool + LangGraph pipeline
to test HTTP-level behavior without any real external calls.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# We import the app AFTER patching to avoid heavy module-level side-effects
@pytest.fixture(scope="module")
def app():
    """Lazily import the FastAPI app inside the fixture to avoid missing-env crashes."""
    import os
    os.environ.setdefault("API_KEY", "test-key")
    os.environ.setdefault("GROQ_API_KEY", "test-groq")
    os.environ.setdefault("HUGGINGFACE_API_KEY", "test-hf")
    os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
    os.environ.setdefault("SUPABASE_KEY", "mock-key")

    from backend.main import app as fastapi_app
    return fastapi_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health_check(app):
    """The /health endpoint must always return 200 with no auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_start_job_requires_api_key(app):
    """Requests without X-Api-Key must be rejected with 422 (missing header)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/jobs/start", json={"raw_prompt": "A warrior fights in rain", "chat_id": "123"})
    # FastAPI returns 422 when a required header is missing (depend validation)
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_start_job_with_invalid_key(app):
    """Wrong API key must be rejected with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/jobs/start",
            json={"raw_prompt": "A warrior fights in rain", "chat_id": "123"},
            headers={"x-api-key": "wrong-key"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
@patch("backend.main._enqueue_or_fallback", new_callable=AsyncMock, return_value="MOCK_ARQ")
@patch("backend.utils_auth.get_supabase_client")
async def test_start_job_dispatches(mock_supabase, mock_enqueue, app):
    """
    A valid request with the correct API key should return 200 and a job_id.
    The actual pipeline dispatch is mocked.
    """
    mock_supabase.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/jobs/start",
            json={"raw_prompt": "A pirate ship battles in a storm at midnight", "chat_id": "456"},
            headers={"x-api-key": "test-key"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "INITIALIZING"


@pytest.mark.asyncio
@patch("backend.main._enqueue_or_fallback", new_callable=AsyncMock, return_value="MOCK_ARQ")
async def test_resume_job_invalid_action(mock_enqueue, app):
    """The action field must match ^(APPROVE|REJECT|REGENERATE)$ — anything else is 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/jobs/some-job-id/resume",
            json={"action": "DELETE_EVERYTHING"},
            headers={"x-api-key": "test-key"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
@patch("backend.main._enqueue_or_fallback", new_callable=AsyncMock, return_value="MOCK_ARQ")
async def test_resume_job_valid(mock_enqueue, app):
    """A valid APPROVE action should return 200 and RESUMING status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/jobs/abc-123/resume",
            json={"action": "APPROVE"},
            headers={"x-api-key": "test-key"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESUMING"
    assert data["action_received"] == "APPROVE"


@pytest.mark.asyncio
async def test_start_job_prompt_too_short(app):
    """Prompts shorter than 10 characters must fail validation with 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/jobs/start",
            json={"raw_prompt": "hi", "chat_id": "123"},
            headers={"x-api-key": "test-key"},
        )
    assert resp.status_code == 422
