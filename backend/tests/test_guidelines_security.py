"""
Security and Integrity Tests for Guideline Extraction & Rule Sets (GE-SEC).
Reference: Guideline Extraction Plan Section 10.15 (GE-SEC-01 to GE-SEC-17).
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.db.models.guideline_extraction import GuidelineExtraction
from app.db.models.guideline_rule import GuidelineRule
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import get_db
from app.services.guidelines.llm.base import Finding
from app.services.guidelines.llm.fake_client import FakeLLMClient
from app.services.guidelines.runner import set_global_llm_client


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


@pytest.fixture
def test_user_a(db_session):
    from app.core.security import create_access_token
    u = db_session.scalars(select(User).where(User.email == "sec_user_a@example.com")).first()
    if not u:
        u = User(email="sec_user_a@example.com", password_hash="pw", full_name="User Sec A")
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    token = create_access_token(u.user_id)
    return u, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user_b(db_session):
    from app.core.security import create_access_token
    u = db_session.scalars(select(User).where(User.email == "sec_user_b@example.com")).first()
    if not u:
        u = User(email="sec_user_b@example.com", password_hash="pw", full_name="User Sec B")
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    token = create_access_token(u.user_id)
    return u, {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_ge_sec_01_unauthenticated_endpoints():
    """GE-SEC-01: Every endpoint without a token returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        endpoints = [
            ("POST", "/guidelines/extractions"),
            ("GET", "/guidelines/extractions"),
            ("GET", "/guidelines/extractions/1"),
            ("POST", "/guidelines/extractions/1/cancel"),
            ("POST", "/guidelines/extractions/1/retry"),
            ("POST", "/guidelines/extractions/1/confirm"),
            ("DELETE", "/guidelines/extractions/1"),
            ("POST", "/guidelines/rule-sets"),
            ("GET", "/guidelines/rule-sets"),
            ("GET", "/guidelines/rule-sets/1"),
            ("PATCH", "/guidelines/rule-sets/1"),
            ("GET", "/guidelines/rule-sets/1/versions"),
            ("POST", "/guidelines/rule-sets/1/activate"),
            ("POST", "/guidelines/rule-sets/1/copy"),
            ("DELETE", "/guidelines/rule-sets/1"),
            ("GET", "/journals/1/guidelines"),
            ("PUT", "/projects/1/guidelines/1"),
            ("DELETE", "/projects/1/guidelines"),
            ("GET", "/projects/1/guidelines"),
        ]
        for method, ep in endpoints:
            if method == "GET":
                r = await ac.get(ep)
            elif method == "POST":
                r = await ac.post(ep, json={})
            elif method == "PATCH":
                r = await ac.patch(ep, json={})
            elif method == "PUT":
                r = await ac.put(ep, json={})
            elif method == "DELETE":
                r = await ac.delete(ep)
            assert r.status_code == 401, f"{method} {ep} should return 401 without token, got {r.status_code}"


@pytest.mark.anyio
async def test_ge_sec_02_03_ownership_and_identical_404(test_user_a, test_user_b, db_session):
    """GE-SEC-02, 03: Accessing other user's resources returns 404, identical to unknown IDs."""
    ua, ha = test_user_a
    ub, hb = test_user_b

    # User A's extraction and rule set
    ext_a = GuidelineExtraction(user_id=ua.user_id, source_type="text", status="completed", step="done", schema_version=1)
    rule_a = GuidelineRule(owner_user_id=ua.user_id, name="User A Rules", is_active=True, rules={"schemaVersion": 1, "general": {"maxWords": 5000}}, schema_version=1)
    proj_a = Project(user_id=ua.user_id, project_title="Project A")
    db_session.add_all([ext_a, rule_a, proj_a])
    db_session.commit()
    db_session.refresh(ext_a)
    db_session.refresh(rule_a)
    db_session.refresh(proj_a)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Check User B on User A extraction vs nonexistent
        r_foreign_ext = await ac.get(f"/guidelines/extractions/{ext_a.extraction_id}", headers=hb)
        r_unknown_ext = await ac.get("/guidelines/extractions/999999", headers=hb)
        assert r_foreign_ext.status_code == 404
        assert r_unknown_ext.status_code == 404
        assert r_foreign_ext.json() == r_unknown_ext.json()

        # Check User B on User A rule set vs nonexistent
        r_foreign_rs = await ac.get(f"/guidelines/rule-sets/{rule_a.rule_id}", headers=hb)
        r_unknown_rs = await ac.get("/guidelines/rule-sets/999999", headers=hb)
        assert r_foreign_rs.status_code == 404
        assert r_unknown_rs.status_code == 404
        assert r_foreign_rs.json() == r_unknown_rs.json()

        # User B patch on User A rule set -> 404
        r_patch_foreign = await ac.patch(f"/guidelines/rule-sets/{rule_a.rule_id}", headers=hb, json={"name": "Hacked"})
        assert r_patch_foreign.status_code == 404

        # User B delete on User A rule set -> 404
        r_del_foreign = await ac.delete(f"/guidelines/rule-sets/{rule_a.rule_id}", headers=hb)
        assert r_del_foreign.status_code == 404


@pytest.mark.anyio
async def test_ge_sec_04_mass_assignment_protection(test_user_a, db_session):
    """GE-SEC-04: Mass assignment attempts on write endpoints have no effect."""
    ua, ha = test_user_a
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Attempt to set ownerUserId, origin, isSystem, version in manual create
        malicious_payload = {
            "name": "Normal Name",
            "rules": {"schemaVersion": 1, "general": {"maxWords": 5000}},
            "ownerUserId": 99999,
            "origin": "seed",
            "isSystem": True,
            "version": 42,
            "isActive": False,
        }
        res = await ac.post("/guidelines/rule-sets", headers=ha, json=malicious_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["origin"] == "manual"  # Enforced by server
        assert data["version"] == 1        # Enforced by server
        assert data["isSystem"] is False   # Enforced by server
        assert data["isActive"] is True    # Enforced by server

        created_id = int(data["id"])
        db_session.expire_all()
        rule = db_session.get(GuidelineRule, created_id)
        assert rule.owner_user_id == ua.user_id  # Real user, not 99999


@pytest.mark.anyio
async def test_ge_sec_08_09_xss_and_sqli_safety(test_user_a, db_session):
    """GE-SEC-08: XSS strings; GE-SEC-09: SQL injection in search and fields."""
    ua, ha = test_user_a
    xss_payload = "<script>alert('xss')</script>"
    sqli_payload = "test' OR '1'='1"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # XSS in name
        r_xss = await ac.post(
            "/guidelines/rule-sets",
            headers=ha,
            json={"name": xss_payload, "rules": {"schemaVersion": 1, "general": {"maxWords": 5000}}},
        )
        assert r_xss.status_code == 201
        assert r_xss.json()["name"] == xss_payload  # Stored cleanly as plain text

        # SQL Injection in search query
        r_sqli = await ac.get(f"/guidelines/rule-sets?search={sqli_payload}", headers=ha)
        assert r_sqli.status_code == 200
        # Returns 0 results or matching text, no DB error or table dump
        assert isinstance(r_sqli.json()["items"], list)


@pytest.mark.anyio
async def test_ge_sec_10_large_payload_rejected(test_user_a):
    """GE-SEC-10: Text over 200,000 characters rejected with 422."""
    _, ha = test_user_a
    huge_text = "word " * 45000  # > 220,000 characters
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/guidelines/extractions",
            headers=ha,
            json={"sourceType": "text", "text": huge_text},
        )
        assert res.status_code == 422
        assert "exceeds maximum length" in res.text.lower()


@pytest.mark.anyio
async def test_ge_sec_15_pasted_text_user_isolation(test_user_a, test_user_b, db_session):
    """GE-SEC-15: Pasted text is never exposed in responses or visible to other users."""
    ua, ha = test_user_a
    ub, hb = test_user_b

    secret_text = "Private unpublished research guidelines text with unique confidential token XYZ123." * 5
    job = GuidelineExtraction(
        user_id=ua.user_id,
        source_type="text",
        source_text=secret_text,
        status="completed",
        step="done",
        schema_version=1,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # User A's GET response does NOT include source_text
        r_a = await ac.get(f"/guidelines/extractions/{job.extraction_id}", headers=ha)
        assert r_a.status_code == 200
        assert "sourceText" not in r_a.json()
        assert "XYZ123" not in r_a.text

        # User B cannot access User A's extraction at all
        r_b = await ac.get(f"/guidelines/extractions/{job.extraction_id}", headers=hb)
        assert r_b.status_code == 404
