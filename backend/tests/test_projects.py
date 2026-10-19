import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.project_journal import ProjectJournal
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
        review_weeks=10,
        acceptance_rate=12.0,
    )
    db_session.add(journal)
    db_session.flush()
    return journal


def test_projects_requires_auth(client):
    res_get = client.get("/projects")
    assert res_get.status_code == 401

    res_post = client.post("/projects", json={"title": "No Auth Proj"})
    assert res_post.status_code == 401


def test_projects_crud_happy_path(client, auth_header_a):
    # 1. Create project
    create_res = client.post(
        "/projects",
        json={
            "title": "Quantum Deep Learning",
            "abstract": "We explore quantum tensor networks for machine learning.",
            "keywords": ["quantum", "tensors", "deep learning"],
        },
        headers=auth_header_a,
    )
    assert create_res.status_code == 201
    p_data = create_res.json()
    assert "id" in p_data
    assert p_data["title"] == "Quantum Deep Learning"
    assert p_data["abstract"] == "We explore quantum tensor networks for machine learning."
    assert p_data["keywords"] == ["quantum", "tensors", "deep learning"]
    assert p_data["wordCount"] == 8
    p_id = p_data["id"]

    # 2. List projects
    list_res = client.get("/projects", headers=auth_header_a)
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(item["id"] == p_id for item in items)

    # 3. Get single project
    get_res = client.get(f"/projects/{p_id}", headers=auth_header_a)
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Quantum Deep Learning"

    # 4. Update project
    update_res = client.put(
        f"/projects/{p_id}",
        json={
            "title": "Quantum Deep Learning 2.0",
            "abstract": "Updated abstract with more words.",
            "keywords": ["quantum", "neural"],
        },
        headers=auth_header_a,
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["title"] == "Quantum Deep Learning 2.0"
    assert updated_data["keywords"] == ["quantum", "neural"]

    # 5. Delete project
    del_res = client.delete(f"/projects/{p_id}", headers=auth_header_a)
    assert del_res.status_code == 200

    # 6. Verify 404 after deletion
    get_del = client.get(f"/projects/{p_id}", headers=auth_header_a)
    assert get_del.status_code == 404


def test_cross_user_isolation_returns_404(client, auth_header_a, auth_header_b):
    # User A creates a project
    create_res = client.post(
        "/projects",
        json={"title": "Alpha Confidential Project"},
        headers=auth_header_a,
    )
    assert create_res.status_code == 201
    p_id = create_res.json()["id"]

    # User B attempts to access User A's project -> MUST return 404, never 403
    assert client.get(f"/projects/{p_id}", headers=auth_header_b).status_code == 404
    assert client.put(f"/projects/{p_id}", json={"title": "Hacked"}, headers=auth_header_b).status_code == 404
    assert client.delete(f"/projects/{p_id}", headers=auth_header_b).status_code == 404
    assert client.get(f"/projects/{p_id}/shortlist", headers=auth_header_b).status_code == 404
    assert client.put(f"/projects/{p_id}/shortlist/1", headers=auth_header_b).status_code == 404
    assert client.delete(f"/projects/{p_id}/shortlist/1", headers=auth_header_b).status_code == 404


def test_shortlist_idempotency_and_lifecycle(
    client, auth_header_a, sample_journal
):
    # 1. Create project
    create_res = client.post(
        "/projects",
        json={"title": "My Shortlist Project"},
        headers=auth_header_a,
    )
    p_id = create_res.json()["id"]
    j_id = sample_journal.journal_id

    # 2. Shortlist journal
    sl_res = client.put(
        f"/projects/{p_id}/shortlist/{j_id}",
        json={"similarityScore": 0.895},
        headers=auth_header_a,
    )
    assert sl_res.status_code == 200
    sl_data = sl_res.json()
    assert sl_data["isShortlisted"] is True
    assert sl_data["matchScore"] == 90
    assert sl_data["rawSimilarity"] == 0.895

    # 3. Idempotent PUT
    sl_res2 = client.put(
        f"/projects/{p_id}/shortlist/{j_id}",
        json={"similarityScore": 0.91},
        headers=auth_header_a,
    )
    assert sl_res2.status_code == 200
    assert sl_res2.json()["matchScore"] == 91

    # 4. Get shortlist
    list_sl = client.get(f"/projects/{p_id}/shortlist", headers=auth_header_a)
    assert list_sl.status_code == 200
    items = list_sl.json()
    assert len(items) == 1
    assert items[0]["id"] == str(j_id)
    assert items[0]["isShortlisted"] is True

    # 5. Non-existent journal 404
    bad_j = client.put(f"/projects/{p_id}/shortlist/999999", headers=auth_header_a)
    assert bad_j.status_code == 404

    # 6. Unshortlist
    un_res = client.delete(f"/projects/{p_id}/shortlist/{j_id}", headers=auth_header_a)
    assert un_res.status_code == 200
    assert un_res.json()["isShortlisted"] is False

    # 7. Shortlist is now empty
    list_empty = client.get(f"/projects/{p_id}/shortlist", headers=auth_header_a)
    assert list_empty.status_code == 200
    assert len(list_empty.json()) == 0


def test_delete_project_cascades_shortlist(
    client, db_session, auth_header_a, sample_journal
):
    create_res = client.post(
        "/projects",
        json={"title": "Cascade Test Project"},
        headers=auth_header_a,
    )
    p_id = int(create_res.json()["id"])
    j_id = sample_journal.journal_id

    client.put(
        f"/projects/{p_id}/shortlist/{j_id}",
        headers=auth_header_a,
    )

    # Verify ProjectJournal exists
    pj_check = db_session.execute(
        select(ProjectJournal).where(
            ProjectJournal.project_id == p_id,
            ProjectJournal.journal_id == j_id,
        )
    ).scalar_one_or_none()
    assert pj_check is not None

    # Delete project
    del_res = client.delete(f"/projects/{p_id}", headers=auth_header_a)
    assert del_res.status_code == 200

    # Verify ProjectJournal was cascade deleted
    pj_after = db_session.execute(
        select(ProjectJournal).where(
            ProjectJournal.project_id == p_id,
            ProjectJournal.journal_id == j_id,
        )
    ).scalar_one_or_none()
    assert pj_after is None
