import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.models.journal import Journal
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
def auth_header(db_session):
    # Create a test researcher
    user = User(
        full_name="Browse Tester",
        email="browse_tester@example.com",
        password_hash="fakehash",
    )
    db_session.add(user)
    db_session.flush()

    token = create_access_token(user.user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_journals(db_session):
    # Insert a few sample journals for isolated test assertions
    j1 = Journal(
        journal_title="IEEE Transactions on Computing AI",
        publisher="IEEE",
        issn="1111-2222",
        subject_category="Artificial Intelligence",
        citescore=15.5,
        impact_factor=8.2,
        quartile="Q1",
        aims_and_scope="Machine learning and artificial intelligence scopes.",
        open_access_type="Hybrid",
        review_weeks=12,
        acceptance_rate=18.0,
    )
    j2 = Journal(
        journal_title="ACM Transactions on Graphics Special",
        publisher="ACM",
        issn="3333-4444",
        subject_category="Computer Graphics",
        citescore=10.2,
        impact_factor=5.1,
        quartile="Q2",
        aims_and_scope="Computer graphics rendering and geometry processing.",
        open_access_type="Open access",
        review_weeks=16,
        acceptance_rate=25.0,
    )
    j3 = Journal(
        journal_title="Elsevier Journal of Systems Engineering",
        publisher="Elsevier",
        issn="5555-6666",
        subject_category="Software Engineering",
        citescore=7.0,
        impact_factor=3.5,
        quartile="Q3",
        aims_and_scope="Software architectures, testing and verification.",
        open_access_type="Subscription",
        review_weeks=14,
        acceptance_rate=30.0,
    )
    db_session.add_all([j1, j2, j3])
    db_session.flush()
    return [j1, j2, j3]


def test_browse_journals_requires_auth(client):
    res = client.get("/journals/browse")
    assert res.status_code == 401


def test_browse_journals_authenticated_returns_paginated_list(client, sample_journals, auth_header):
    res = client.get("/journals/browse?limit=2&page=1", headers=auth_header)
    assert res.status_code == 200
    data = res.json()

    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert "totalPages" in data
    assert "categories" in data
    assert "publishers" in data

    assert len(data["items"]) == 2
    assert data["total"] >= 3
    assert data["page"] == 1
    assert data["limit"] == 2


def test_browse_journals_filter_by_publisher(client, sample_journals, auth_header):
    res = client.get("/journals/browse?publisher=ACM", headers=auth_header)
    assert res.status_code == 200
    data = res.json()

    assert all(item["publisher"] == "ACM" for item in data["items"])
    assert any("Graphics" in item["title"] for item in data["items"])


def test_browse_journals_filter_by_quartile(client, sample_journals, auth_header):
    res = client.get("/journals/browse?quartile=Q1", headers=auth_header)
    assert res.status_code == 200
    data = res.json()

    assert all(item["quartile"] == "Q1" for item in data["items"])


def test_browse_journals_search_keyword(client, sample_journals, auth_header):
    res = client.get("/journals/browse?search=Rendering", headers=auth_header)
    assert res.status_code == 200
    data = res.json()

    assert len(data["items"]) >= 1
    assert any("Graphics" in item["title"] for item in data["items"])


def test_get_single_journal(client, sample_journals, auth_header):
    target_id = sample_journals[0].journal_id

    res = client.get(f"/journals/{target_id}", headers=auth_header)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(target_id)
    assert data["title"] == sample_journals[0].journal_title

    # 404 for invalid id
    res404 = client.get("/journals/999999", headers=auth_header)
    assert res404.status_code == 404
