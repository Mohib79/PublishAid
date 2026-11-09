import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.project_journal import ProjectJournal
from app.db.models.activity_log import ActivityLog
from app.db.models.user import User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user_a(db_session):
    user = User(
        full_name="User Alpha",
        email="alpha@example.com",
        password_hash="hash_a",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def auth_header_a(user_a):
    token = create_access_token(user_a.user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_b(db_session):
    user = User(
        full_name="User Beta",
        email="beta@example.com",
        password_hash="hash_b",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def auth_header_b(user_b):
    token = create_access_token(user_b.user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_journal(db_session):
    journal = Journal(
        journal_title="Nature Computer Intelligence",
        publisher="Springer",
        issn="9999-0001",
        subject_category="Computer Science",
        citescore=20.0,
        impact_factor=15.0,
        quartile="Q1",
        aims_and_scope="Pioneering artificial intelligence scope.",
        open_access_type="Open access",
        review_weeks=10.0,
        acceptance_rate=12.0,
    )
    db_session.add(journal)
    db_session.flush()
    return journal


# --- Authentication & Authorization ---

def test_projects_requires_auth(client):
    res_get = client.get("/projects")
    assert res_get.status_code == 401

    res_post = client.post("/projects", json={"title": "No Auth Proj"})
    assert res_post.status_code == 401


def test_cross_user_isolation_returns_404(client, auth_header_a, auth_header_b):
    create_res = client.post(
        "/projects",
        json={"title": "Alpha Confidential Project"},
        headers=auth_header_a,
    )
    assert create_res.status_code == 201
    p_id = create_res.json()["id"]

    # Unknown vs foreign project ID returns identical 404
    assert client.get(f"/projects/{p_id}", headers=auth_header_b).status_code == 404
    assert client.get("/projects/999999", headers=auth_header_b).status_code == 404

    assert client.patch(f"/projects/{p_id}", json={"title": "Hacked"}, headers=auth_header_b).status_code == 404
    assert client.delete(f"/projects/{p_id}", headers=auth_header_b).status_code == 404
    assert client.get(f"/projects/{p_id}/shortlist", headers=auth_header_b).status_code == 404
    assert client.get(f"/projects/{p_id}/activity", headers=auth_header_b).status_code == 404


# --- Create Projects (WS-CRE) ---

def test_create_project_validation_and_creation(client, auth_header_a):
    # WS-CRE-01: Valid body with title
    res1 = client.post("/projects", json={"title": "  Quantum   Computing  "}, headers=auth_header_a)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["title"] == "Quantum Computing"  # Whitespace collapsed
    assert data1["status"] == "draft"
    assert data1["id"] is not None
    assert isinstance(data1["id"], str)
    assert "createdAt" in data1
    assert "updatedAt" in data1

    # WS-CRE-03 & 04: Blank title rejected with 422
    res_empty = client.post("/projects", json={"title": "   "}, headers=auth_header_a)
    assert res_empty.status_code == 422

    # WS-CRE-05: Title > 300 chars rejected
    res_long = client.post("/projects", json={"title": "A" * 301}, headers=auth_header_a)
    assert res_long.status_code == 422

    # WS-CRE-09: Status in body is ignored on create
    res_status = client.post("/projects", json={"title": "Status Test", "status": "submitted"}, headers=auth_header_a)
    assert res_status.status_code == 201
    assert res_status.json()["status"] == "draft"


def test_create_project_keyword_normalization(client, auth_header_a):
    res = client.post(
        "/projects",
        json={
            "title": "Keyword Paper",
            "keywords": ["AI", " ai ", "Deep Learning", "ai", "", "Optimization"],
        },
        headers=auth_header_a,
    )
    assert res.status_code == 201
    kw = res.json()["keywords"]
    assert kw == ["AI", "Deep Learning", "Optimization"]  # Trimmed, blanks removed, deduplicated case-insensitively


# --- List Projects (WS-LST) ---

def test_list_projects_pagination_search_sort(client, auth_header_a, db_session, user_a):
    for i in range(15):
        p = Project(
            user_id=user_a.user_id,
            project_title=f"Paper {i:02d} on Neural Nets",
            research_field="Computer Science" if i % 2 == 0 else "Physics",
            status="draft" if i % 2 == 0 else "in_progress",
        )
        db_session.add(p)
    db_session.commit()

    # List page 1, size 10
    res = client.get("/projects?page=1&pageSize=10", headers=auth_header_a)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 15
    assert len(data["items"]) == 10
    assert data["page"] == 1
    assert data["pageSize"] == 10

    # Search filter
    res_search = client.get("/projects?search=Physics", headers=auth_header_a)
    assert res_search.status_code == 200
    for item in res_search.json()["items"]:
        assert "physics" in item["researchField"].lower() or "physics" in item["title"].lower()

    # Status filter
    res_status = client.get("/projects?status=in_progress", headers=auth_header_a)
    assert res_status.status_code == 200
    for item in res_status.json()["items"]:
        assert item["status"] == "in_progress"


# --- Get Overview (WS-GET) ---

def test_get_project_overview(client, auth_header_a):
    create_res = client.post(
        "/projects",
        json={"title": "Overview Test", "researchField": "Robotics", "abstract": "Robotics study."},
        headers=auth_header_a,
    )
    p_id = create_res.json()["id"]

    res = client.get(f"/projects/{p_id}", headers=auth_header_a)
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Overview Test"
    assert data["researchField"] == "Robotics"
    assert data["counts"]["conversions"] == 0
    assert data["counts"]["complianceReports"] == 0
    assert len(data["recentActivity"]) >= 1
    assert data["recentActivity"][0]["eventType"] == "project_created"


# --- Patch Project (WS-UPD) ---

def test_patch_project(client, auth_header_a):
    create_res = client.post("/projects", json={"title": "Original Title"}, headers=auth_header_a)
    p_id = create_res.json()["id"]

    # Patch title and status
    patch_res = client.patch(
        f"/projects/{p_id}",
        json={"title": "Updated Title", "status": "in_progress"},
        headers=auth_header_a,
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["title"] == "Updated Title"
    assert data["status"] == "in_progress"

    # Empty patch body returns 422
    assert client.patch(f"/projects/{p_id}", json={}, headers=auth_header_a).status_code == 422


# --- Delete Project (WS-DEL) ---

def test_delete_project_returns_204(client, auth_header_a):
    create_res = client.post("/projects", json={"title": "To Delete"}, headers=auth_header_a)
    p_id = create_res.json()["id"]

    del_res = client.delete(f"/projects/{p_id}", headers=auth_header_a)
    assert del_res.status_code == 204

    # Second delete returns 404
    assert client.delete(f"/projects/{p_id}", headers=auth_header_a).status_code == 404
    assert client.get(f"/projects/{p_id}", headers=auth_header_a).status_code == 404


# --- Activity Log Endpoints ---

def test_activity_log_feed(client, auth_header_a):
    create_res = client.post("/projects", json={"title": "Activity Project"}, headers=auth_header_a)
    p_id = create_res.json()["id"]

    client.patch(f"/projects/{p_id}", json={"status": "in_progress"}, headers=auth_header_a)

    # Project activity
    res_proj = client.get(f"/projects/{p_id}/activity", headers=auth_header_a)
    assert res_proj.status_code == 200
    events = res_proj.json()
    assert len(events) >= 2
    types = [e["eventType"] for e in events]
    assert "project_created" in types
    assert "project_status_changed" in types

    # Recent global activity feed
    res_recent = client.get("/activity/recent", headers=auth_header_a)
    assert res_recent.status_code == 200
    assert len(res_recent.json()) >= 2


# --- Part B: Target Journal Tests (WS-TGT) ---

def test_target_journal_lifecycle(client, auth_header_a, sample_journal):
    create_res = client.post("/projects", json={"title": "Target Journal Project"}, headers=auth_header_a)
    p_id = create_res.json()["id"]
    j_id = sample_journal.journal_id

    # 1. Set target journal (WS-TGT-01 & 02)
    set_res = client.put(f"/projects/{p_id}/target-journal/{j_id}", headers=auth_header_a)
    assert set_res.status_code == 200
    data = set_res.json()
    assert data["targetJournal"] is not None
    assert data["targetJournal"]["id"] == str(j_id)
    assert data["shortlistedCount"] >= 1

    # 2. Clear target journal (WS-TGT-07)
    clear_res = client.delete(f"/projects/{p_id}/target-journal", headers=auth_header_a)
    assert clear_res.status_code == 200
    data_cleared = clear_res.json()
    assert data_cleared["targetJournal"] is None
    # Remains shortlisted
    assert data_cleared["shortlistedCount"] >= 1


# --- Part B: Upload & Manuscript Tests (WS-UPL, WS-MDL) ---

def test_manuscript_upload_and_delete(client, auth_header_a):
    create_res = client.post("/projects", json={"title": "Upload Paper Project"}, headers=auth_header_a)
    p_id = create_res.json()["id"]

    # 1. Upload valid .tex file
    tex_content = b"\\documentclass{article}\n\\begin{document}\nHello PublishAid\n\\end{document}"
    files = {"file": ("draft.tex", tex_content, "text/plain")}
    up_res = client.post(f"/projects/{p_id}/manuscript", files=files, headers=auth_header_a)
    assert up_res.status_code == 201
    up_data = up_res.json()
    assert up_data["fileName"] == "draft.tex"
    assert up_data["sizeBytes"] == len(tex_content)
    assert up_data["available"] is True
    assert "expiresAt" in up_data

    # 2. Verify overview reflects manuscript
    ov_res = client.get(f"/projects/{p_id}", headers=auth_header_a)
    assert ov_res.status_code == 200
    ov_data = ov_res.json()
    assert ov_data["manuscript"] is not None
    assert ov_data["manuscript"]["fileName"] == "draft.tex"

    # 3. Reject invalid file extension (.exe)
    bad_files = {"file": ("malicious.exe", b"binarycontent", "application/octet-stream")}
    bad_res = client.post(f"/projects/{p_id}/manuscript", files=bad_files, headers=auth_header_a)
    assert bad_res.status_code == 415

    # 4. Reject empty file
    empty_files = {"file": ("empty.tex", b"", "text/plain")}
    empty_res = client.post(f"/projects/{p_id}/manuscript", files=empty_files, headers=auth_header_a)
    assert empty_res.status_code == 422

    # 5. Delete manuscript (WS-MDL-01)
    del_res = client.delete(f"/projects/{p_id}/manuscript", headers=auth_header_a)
    assert del_res.status_code == 204

    # 6. Delete when none attached returns 404
    assert client.delete(f"/projects/{p_id}/manuscript", headers=auth_header_a).status_code == 404

