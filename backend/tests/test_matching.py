import pytest
from fastapi.testclient import TestClient

from app.core.embeddings_config import EMBEDDING_DIMENSION
from app.core.security import create_access_token
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.project_journal import ProjectJournal
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.services.embedding import get_embedder


class FakeEmbedder:
    def __init__(self, vector: list[float] | None = None):
        if vector is None:
            # Default unit vector along axis 0
            v = [0.0] * EMBEDDING_DIMENSION
            v[0] = 1.0
            self.vector = v
        else:
            self.vector = vector

    def embed_query(self, text: str) -> list[float]:
        return self.vector


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture
def client(db_session, fake_embedder):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    user = User(
        full_name="Match Tester",
        email="match_tester@example.com",
        password_hash="fakehash",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def auth_header(test_user):
    token = create_access_token(test_user.user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def vector_journals(db_session):
    # Vector j1 aligned with axis 0 (distance 0 to [1, 0, ...])
    v1 = [0.0] * EMBEDDING_DIMENSION
    v1[0] = 1.0

    # Vector j2 orthogonal (distance 1.0 to [1, 0, ...])
    v2 = [0.0] * EMBEDDING_DIMENSION
    v2[1] = 1.0

    # Vector j3 partially aligned (e.g. angle ~ 45 deg)
    v3 = [0.0] * EMBEDDING_DIMENSION
    v3[0] = 0.7071
    v3[1] = 0.7071

    j1 = Journal(
        journal_title="Journal of Perfect Fit",
        publisher="Top Publisher",
        issn="1000-0001",
        subject_category="Computer Science",
        citescore=12.0,
        impact_factor=6.5,
        quartile="Q1",
        aims_and_scope="Perfect match for the test vector.",
        open_access_type="Open access",
        review_weeks=8,
        acceptance_rate=20.0,
        embedding=v1,
    )
    j2 = Journal(
        journal_title="Journal of Orthogonal Topics",
        publisher="Other Publisher",
        issn="1000-0002",
        subject_category="Mathematics",
        citescore=None,
        impact_factor=None,
        quartile=None,
        aims_and_scope="Unrelated topic completely.",
        open_access_type="Subscription",
        review_weeks=None,
        acceptance_rate=None,
        embedding=v2,
    )
    j3 = Journal(
        journal_title="Journal of Moderate Fit",
        publisher="Mid Publisher",
        issn="1000-0003",
        subject_category="Data Science",
        citescore=8.5,
        impact_factor=4.0,
        quartile="Q2",
        aims_and_scope="Moderate match for the test vector.",
        open_access_type="Hybrid",
        review_weeks=14,
        acceptance_rate=35.0,
        embedding=v3,
    )
    db_session.add_all([j1, j2, j3])
    db_session.flush()
    return [j1, j2, j3]


def test_match_journals_requires_auth(client):
    res = client.post("/journals/match", json={"title": "Test", "abstract": "Abstract"})
    assert res.status_code == 401


def test_match_journals_empty_input_returns_422(client, auth_header):
    # Both title and abstract empty/missing
    res = client.post("/journals/match", json={"title": "", "abstract": "   "}, headers=auth_header)
    assert res.status_code == 422


def test_match_journals_valid_with_only_title_or_only_abstract(client, auth_header, vector_journals):
    res1 = client.post("/journals/match", json={"title": "Deep Learning Vision"}, headers=auth_header)
    assert res1.status_code == 200

    res2 = client.post(
        "/journals/match",
        json={"abstract": "This study investigates autonomous vehicles navigation."},
        headers=auth_header,
    )
    assert res2.status_code == 200


def test_match_journals_ranking_and_scores(client, auth_header, vector_journals):
    res = client.post(
        "/journals/match",
        json={
            "title": "Target manuscript",
            "abstract": "Aligned with test vector axis 0",
            "limit": 10,
        },
        headers=auth_header,
    )
    assert res.status_code == 200
    data = res.json()

    assert "results" in data
    assert "meta" in data
    assert len(data["results"]) >= 3

    results = data["results"]
    # j1 should be top ranked
    top = results[0]
    assert top["title"] == "Journal of Perfect Fit"
    assert top["matchScore"] == 100
    assert top["matchTag"] == "Best fit"
    assert top["rawSimilarity"] >= 0.99
    assert top["isShortlisted"] is False

    # j3 should be ranked above j2
    titles = [r["title"] for r in results]
    assert titles.index("Journal of Perfect Fit") < titles.index("Journal of Moderate Fit")
    assert titles.index("Journal of Moderate Fit") < titles.index("Journal of Orthogonal Topics")


def test_match_journals_null_metrics_preserved(client, auth_header, vector_journals):
    res = client.post(
        "/journals/match",
        json={"title": "Test", "abstract": "Test abstract"},
        headers=auth_header,
    )
    assert res.status_code == 200
    data = res.json()

    # Find the orthogonal journal with null metrics
    ortho = next(r for r in data["results"] if r["title"] == "Journal of Orthogonal Topics")
    assert ortho["citeScore"] is None
    assert ortho["impactFactor"] is None
    assert ortho["quartile"] is None
    assert ortho["reviewWeeks"] is None
    assert ortho["acceptanceRate"] is None


def test_match_journals_project_authorization_and_shortlisting(
    client, db_session, test_user, auth_header, vector_journals
):
    # 1. Create a project for test_user
    project = Project(
        user_id=test_user.user_id,
        project_title="User 1 Project",
        manuscript_abstract="Sample abstract",
    )
    db_session.add(project)
    db_session.flush()

    # Shortlist j1 in this project
    pj = ProjectJournal(
        project_id=project.project_id,
        journal_id=vector_journals[0].journal_id,
        similarity_score=0.98,
        is_shortlisted=True,
        is_selected=False,
    )
    db_session.add(pj)
    db_session.flush()

    # Query with projectId = project.project_id
    res = client.post(
        "/journals/match",
        json={
            "title": "Test",
            "abstract": "Abstract",
            "projectId": str(project.project_id),
        },
        headers=auth_header,
    )
    assert res.status_code == 200
    data = res.json()
    top = next(r for r in data["results"] if r["title"] == "Journal of Perfect Fit")
    assert top["isShortlisted"] is True

    other = next(r for r in data["results"] if r["title"] == "Journal of Moderate Fit")
    assert other["isShortlisted"] is False

    # 2. Query with nonexistent project -> 404
    res_nonexistent = client.post(
        "/journals/match",
        json={"title": "Test", "abstract": "Abstract", "projectId": "999999"},
        headers=auth_header,
    )
    assert res_nonexistent.status_code == 404

    # 3. Create another user and project
    user2 = User(
        full_name="User Two",
        email="user2@example.com",
        password_hash="fakehash",
    )
    db_session.add(user2)
    db_session.flush()

    project2 = Project(
        user_id=user2.user_id,
        project_title="User 2 Project",
    )
    db_session.add(project2)
    db_session.flush()

    # Query with user2's project using user1's auth header -> 404 (do not leak existence)
    res_other_user = client.post(
        "/journals/match",
        json={"title": "Test", "abstract": "Abstract", "projectId": str(project2.project_id)},
        headers=auth_header,
    )
    assert res_other_user.status_code == 404


@pytest.mark.slow
def test_match_journals_real_embedder(db_session, auth_header, vector_journals):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    # Do NOT override get_embedder so it uses the real model
    try:
        real_client = TestClient(app)
        res = real_client.post(
            "/journals/match",
            json={
                "title": "Deep Residual Learning for Image Recognition",
                "abstract": "Deeper neural networks are more difficult to train. We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously.",
                "keywords": ["deep learning", "neural networks", "image recognition"],
                "limit": 5,
            },
            headers=auth_header,
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["results"]) > 0
        assert data["meta"]["model"] == "allenai-specter"
        assert "tookMs" in data["meta"]
        # Match score must be between 0 and 100
        assert 0 <= data["results"][0]["matchScore"] <= 100
    finally:
        app.dependency_overrides.clear()

