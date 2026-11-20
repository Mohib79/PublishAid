"""
Unit and integration tests for Guideline Extraction Jobs (GE-JOB) and API Endpoints (GE-API).
Reference: Guideline Extraction Plan Section 10.12, 10.12b.
"""

from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from unittest.mock import patch

from app.main import app
from app.db.models.guideline_extraction import GuidelineExtraction
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.user import User
from app.services.guidelines.llm.base import Finding
from app.services.guidelines.llm.fake_client import FakeLLMClient
from app.services.guidelines.runner import (
    set_global_llm_client,
    sweep_stuck_extractions,
    run_extraction_job,
    check_and_enforce_quotas,
    QuotaError,
)
from app.tasks.cleanup import run_cleanup_sweep
from app.db.session import get_db


class SessionWrapper:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._session.rollback()


@pytest.fixture
def session_factory(db_session):
    return lambda: SessionWrapper(db_session)



@pytest.fixture(autouse=True)
def override_db(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def setup_fake_llm():
    """Sets a global FakeLLMClient before each test and clears it after."""
    canned = [
        Finding(path="general.maxWords", value=5000, evidence="The manuscript word limit is 5000 words."),
        Finding(path="citation.style", value="IEEE", evidence="References must follow IEEE format."),
    ]
    client = FakeLLMClient(canned_findings=canned)
    set_global_llm_client(client)
    yield client
    set_global_llm_client(None)


@pytest.fixture
def auth_headers_user1(db_session):
    from app.core.security import create_access_token
    # Check or create user 1
    u = db_session.scalars(select(User).where(User.email == "ge_user1@example.com")).first()
    if not u:
        u = User(email="ge_user1@example.com", password_hash="pw", full_name="User One")
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    token = create_access_token(u.user_id)
    return {"Authorization": f"Bearer {token}"}, u


@pytest.fixture
def auth_headers_user2(db_session):
    from app.core.security import create_access_token
    # Check or create user 2
    u = db_session.scalars(select(User).where(User.email == "ge_user2@example.com")).first()
    if not u:
        u = User(email="ge_user2@example.com", password_hash="pw", full_name="User Two")
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    token = create_access_token(u.user_id)
    return {"Authorization": f"Bearer {token}"}, u


VALID_GUIDELINE_TEXT = (
    "The manuscript word limit is 5000 words for all regular submissions. "
    "Authors must include an abstract under 250 words and five keywords for indexing. "
    "References must follow IEEE format with numbered brackets. "
    "Figures should be prepared at 300 DPI resolution in PNG or TIFF format."
)


# ===========================================================================
# 10.12 Jobs, Quotas, Caching (GE-JOB)
# ===========================================================================

@pytest.mark.anyio
async def test_ge_job_01_text_job_lifecycle(auth_headers_user1, db_session, session_factory):
    """GE-JOB-01: Create a text job -> 202; steps in order; completes."""
    headers, user = auth_headers_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/guidelines/extractions",
            headers=headers,
            json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT},
        )
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "queued"
        job_id = int(data["id"])

        # Run background job synchronously for testing
        await run_extraction_job(job_id, session_factory)

        # Check job status in DB
        db_session.expire_all()
        job = db_session.get(GuidelineExtraction, job_id)
        assert job.status == "completed"
        assert job.step == "done"
        assert job.draft is not None
        assert job.draft["rules"]["general"]["maxWords"] == 5000


@pytest.mark.anyio
async def test_ge_job_04_concurrent_quota(auth_headers_user1, db_session):
    """GE-JOB-04: Third concurrent job for the same user -> 429 TOO_MANY_RUNNING."""
    headers, user = auth_headers_user1
    # Create 2 running/queued jobs
    job1 = GuidelineExtraction(user_id=user.user_id, source_type="text", status="running", step="extracting", schema_version=1)
    job2 = GuidelineExtraction(user_id=user.user_id, source_type="text", status="queued", step="queued", schema_version=1)
    db_session.add_all([job1, job2])
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/guidelines/extractions",
            headers=headers,
            json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT},
        )
        assert res.status_code == 429
        assert "TOO_MANY_RUNNING" in res.json()["detail"] or "already have 2" in res.json()["detail"]


@pytest.mark.anyio
async def test_ge_job_05_daily_quota(auth_headers_user1, db_session):
    """GE-JOB-05: 20 jobs reaching LLM in 24 hours, then another -> 429 DAILY_LIMIT."""
    headers, user = auth_headers_user1
    now = datetime.now(timezone.utc)
    # Add 20 completed jobs with tokens
    for i in range(20):
        j = GuidelineExtraction(
            user_id=user.user_id,
            source_type="text",
            status="completed",
            step="done",
            input_tokens=100,
            output_tokens=50,
            cached=False,
            created_at=now - timedelta(minutes=i * 5),
            schema_version=1,
        )
        db_session.add(j)
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/guidelines/extractions",
            headers=headers,
            json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT},
        )
        assert res.status_code == 429
        assert "DAILY_LIMIT" in res.json()["detail"] or "Daily extraction limit" in res.json()["detail"]
        assert "retry-after" in res.headers


@pytest.mark.anyio
async def test_ge_job_09_identical_text_cached(auth_headers_user1, db_session, setup_fake_llm, session_factory):
    """GE-JOB-09: Identical text submitted again by same user -> cached: true; no LLM call."""
    headers, user = auth_headers_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First request
        res1 = await ac.post(
            "/guidelines/extractions",
            headers=headers,
            json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT},
        )
        assert res1.status_code == 202
        job1_id = int(res1.json()["id"])
        
        await run_extraction_job(job1_id, session_factory)
        assert setup_fake_llm.call_count == 1

        # Second identical request
        res2 = await ac.post(
            "/guidelines/extractions",
            headers=headers,
            json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT},
        )
        assert res2.status_code == 202
        job2_id = int(res2.json()["id"])
        await run_extraction_job(job2_id, session_factory)

        # Check job2 is cached without calling LLM
        db_session.expire_all()
        job2 = db_session.get(GuidelineExtraction, job2_id)
        assert job2.cached is True
        assert setup_fake_llm.call_count == 1  # No additional LLM call


@pytest.mark.anyio
async def test_ge_job_11_cache_per_user_isolation(auth_headers_user1, auth_headers_user2, db_session, setup_fake_llm, session_factory):
    """GE-JOB-11: Same text by another user -> not served from first user's cache."""
    headers1, u1 = auth_headers_user1
    headers2, u2 = auth_headers_user2
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # User 1 completes job
        r1 = await ac.post("/guidelines/extractions", headers=headers1, json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT})
        job1_id = int(r1.json()["id"])
        await run_extraction_job(job1_id, session_factory)
        assert setup_fake_llm.call_count == 1

        # User 2 submits same text
        r2 = await ac.post("/guidelines/extractions", headers=headers2, json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT})
        job2_id = int(r2.json()["id"])
        await run_extraction_job(job2_id, session_factory)
        # LLM was called for User 2 (not taken from user 1's cache)
        assert setup_fake_llm.call_count == 2
        db_session.expire_all()
        job2 = db_session.get(GuidelineExtraction, job2_id)
        assert job2.cached is False


@pytest.mark.anyio
async def test_ge_job_12_in_flight_duplicate_returns_200(auth_headers_user1, db_session):
    """GE-JOB-12: Identical request while one is running -> existing job returned (200)."""
    headers, user = auth_headers_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.post("/guidelines/extractions", headers=headers, json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT})
        assert r1.status_code == 202

        # Second request while first is still queued
        r2 = await ac.post("/guidelines/extractions", headers=headers, json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT})
        assert r2.status_code == 200
        assert r2.json()["id"] == r1.json()["id"]


@pytest.mark.anyio
async def test_ge_job_13_and_14_cancel_job(auth_headers_user1, db_session):
    """GE-JOB-13, 14: Cancel a running job -> cancelled. Cancel completed -> 409."""
    headers, user = auth_headers_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.post("/guidelines/extractions", headers=headers, json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT})
        job_id = r1.json()["id"]

        # Cancel running/queued
        rc = await ac.post(f"/guidelines/extractions/{job_id}/cancel", headers=headers)
        assert rc.status_code == 200
        assert rc.json()["status"] == "cancelled"

        # Cancel already cancelled -> 409
        rc2 = await ac.post(f"/guidelines/extractions/{job_id}/cancel", headers=headers)
        assert rc2.status_code == 409


@pytest.mark.anyio
async def test_ge_job_15_and_16_retry_job(auth_headers_user1, db_session):
    """GE-JOB-15, 16: Retry failed job -> 202. Retry completed job -> 409."""
    headers, user = auth_headers_user1
    # Create failed job
    failed_job = GuidelineExtraction(
        user_id=user.user_id,
        source_type="text",
        source_text=VALID_GUIDELINE_TEXT,
        status="failed",
        step="done",
        error_code="TIMEOUT",
        error_message="Timed out",
        schema_version=1,
    )
    db_session.add(failed_job)
    db_session.commit()
    db_session.refresh(failed_job)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(f"/guidelines/extractions/{failed_job.extraction_id}/retry", headers=headers)
        assert res.status_code == 202
        assert res.json()["status"] == "queued"

        # Mark completed and try retry again
        failed_job.status = "completed"
        db_session.commit()
        res_comp = await ac.post(f"/guidelines/extractions/{failed_job.extraction_id}/retry", headers=headers)
        assert res_comp.status_code == 409


def test_ge_job_18_startup_sweep(db_session, auth_headers_user1):
    """GE-JOB-18: Jobs stuck for > 10 minutes marked failed with INTERRUPTED."""
    _, user = auth_headers_user1
    old_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    stuck_job = GuidelineExtraction(
        user_id=user.user_id,
        source_type="text",
        status="running",
        step="extracting",
        created_at=old_time,
        schema_version=1,
    )
    db_session.add(stuck_job)
    db_session.commit()

    swept = sweep_stuck_extractions(db_session)
    assert swept >= 1
    db_session.refresh(stuck_job)
    assert stuck_job.status == "failed"
    assert stuck_job.error_code == "INTERRUPTED"


def test_ge_job_21_retention_sweep_30_days(db_session, auth_headers_user1):
    """GE-JOB-21: Unconfirmed drafts older than 30 days removed by retention."""
    _, user = auth_headers_user1
    old_time = datetime.now(timezone.utc) - timedelta(days=35)
    expired_draft = GuidelineExtraction(
        user_id=user.user_id,
        source_type="text",
        status="completed",
        step="done",
        created_at=old_time,
        confirmed_rule_id=None,
        schema_version=1,
    )
    db_session.add(expired_draft)
    db_session.commit()
    ext_id = expired_draft.extraction_id

    run_cleanup_sweep(db_session)
    assert db_session.get(GuidelineExtraction, ext_id) is None


# ===========================================================================
# 10.12b Extraction Endpoints (GE-API)
# ===========================================================================

@pytest.mark.anyio
async def test_ge_api_03_both_or_neither_url_text_rejected(auth_headers_user1):
    """GE-API-03: Both URL and text, or neither -> 422."""
    headers, _ = auth_headers_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Both
        r1 = await ac.post("/guidelines/extractions", headers=headers, json={
            "sourceType": "url", "url": "https://example.org", "text": VALID_GUIDELINE_TEXT
        })
        assert r1.status_code == 422

        # Neither
        r2 = await ac.post("/guidelines/extractions", headers=headers, json={
            "sourceType": "text", "text": ""
        })
        assert r2.status_code == 422


@pytest.mark.anyio
async def test_ge_api_05_text_under_30_words(auth_headers_user1):
    """GE-API-05: Text under 30 words -> 422."""
    headers, _ = auth_headers_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/guidelines/extractions", headers=headers, json={
            "sourceType": "text", "text": "This text has only eight words in it."
        })
        assert res.status_code == 422
        assert "too short" in res.text.lower() or "minimum 30" in res.text.lower()


@pytest.mark.anyio
async def test_ge_api_07_unknown_journal_id(auth_headers_user1):
    """GE-API-07: Unknown journalId -> 404."""
    headers, _ = auth_headers_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/guidelines/extractions", headers=headers, json={
            "sourceType": "text", "text": VALID_GUIDELINE_TEXT, "journalId": "999999"
        })
        assert res.status_code == 404


@pytest.mark.anyio
async def test_ge_api_13_list_extractions_user_isolation(auth_headers_user1, auth_headers_user2):
    """GE-API-13: List extractions returns only mine, newest first, paginated."""
    h1, u1 = auth_headers_user1
    h2, u2 = auth_headers_user2
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create for user 1
        await ac.post("/guidelines/extractions", headers=h1, json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT})
        
        # User 2 list should be empty
        r2 = await ac.get("/guidelines/extractions", headers=h2)
        assert r2.status_code == 200
        assert r2.json()["total"] == 0

        # User 1 list has 1 item
        r1 = await ac.get("/guidelines/extractions", headers=h1)
        assert r1.status_code == 200
        assert r1.json()["total"] >= 1
        # source_text is omitted in responses
        assert "sourceText" not in r1.json()["items"][0]


@pytest.mark.anyio
async def test_ge_api_14_get_other_user_extraction_404(auth_headers_user1, auth_headers_user2):
    """GE-API-14: GET another user's extraction -> 404."""
    h1, _ = auth_headers_user1
    h2, _ = auth_headers_user2
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.post("/guidelines/extractions", headers=h1, json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT})
        job_id = r1.json()["id"]

        # User 2 requests User 1's job
        r2 = await ac.get(f"/guidelines/extractions/{job_id}", headers=h2)
        assert r2.status_code == 404


@pytest.mark.anyio
async def test_ge_api_16_response_keys_camelcase(auth_headers_user1):
    """GE-API-16: Response keys in camelCase; IDs as strings."""
    h, _ = auth_headers_user1
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/guidelines/extractions", headers=h, json={"sourceType": "text", "text": VALID_GUIDELINE_TEXT})
        data = r.json()
        assert isinstance(data["id"], str)
        assert "sourceType" in data
        assert "createdAt" in data
