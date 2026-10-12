from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
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


def test_register_success(client):
    payload = {
        "fullName": "Dr. Maya Chen",
        "email": "maya.chen@university.edu",
        "password": "SecurePassword123",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "accessToken" in data
    assert data["tokenType"] == "bearer"
    assert "user" in data
    assert data["user"]["fullName"] == "Dr. Maya Chen"
    assert data["user"]["email"] == "maya.chen@university.edu"
    assert isinstance(data["user"]["id"], str)

    # Ensure no passwords or hashes leak
    raw_text = response.text.lower()
    assert "password_hash" not in raw_text
    assert "passwordhash" not in raw_text


def test_register_duplicate_email(client):
    payload1 = {
        "fullName": "Maya One",
        "email": "duplicate@university.edu",
        "password": "Password123",
    }
    res1 = client.post("/auth/register", json=payload1)
    assert res1.status_code == 201

    # Attempt registration with uppercase variant
    payload2 = {
        "fullName": "Maya Two",
        "email": "DUPLICATE@UNIVERSITY.EDU",
        "password": "Password123",
    }
    res2 = client.post("/auth/register", json=payload2)
    assert res2.status_code == 409
    assert res2.json()["detail"] == "An account with this email already exists"


def test_register_password_shorter_than_8(client):
    payload = {
        "fullName": "Short Pass User",
        "email": "shortpass@university.edu",
        "password": "short7!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422


def test_register_ignores_extra_role_field(client):
    payload = {
        "fullName": "Extra Field User",
        "email": "extrarole@university.edu",
        "password": "ValidPassword123",
        "role": "admin",  # Extra field should be ignored
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "role" not in data["user"]


def test_login_success(client):
    # Register first
    client.post(
        "/auth/register",
        json={
            "fullName": "Login Tester",
            "email": "login_tester@university.edu",
            "password": "CorrectPassword123",
        },
    )

    # Login
    login_res = client.post(
        "/auth/login",
        json={
            "email": "LOGIN_TESTER@university.edu",  # case-insensitive check
            "password": "CorrectPassword123",
        },
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "accessToken" in data
    assert data["tokenType"] == "bearer"
    assert data["user"]["email"] == "login_tester@university.edu"
    assert isinstance(data["user"]["id"], str)

    raw_text = login_res.text.lower()
    assert "password_hash" not in raw_text
    assert "passwordhash" not in raw_text


def test_login_invalid_credentials_identical_message(client):
    # Create account
    client.post(
        "/auth/register",
        json={
            "fullName": "Identical Message User",
            "email": "identical_msg@university.edu",
            "password": "CorrectPassword123",
        },
    )

    # Wrong password on existing email
    res_wrong_pw = client.post(
        "/auth/login",
        json={
            "email": "identical_msg@university.edu",
            "password": "WrongPassword999",
        },
    )
    assert res_wrong_pw.status_code == 401

    # Non-existent email
    res_unknown_email = client.post(
        "/auth/login",
        json={
            "email": "nonexistent_email@university.edu",
            "password": "SomePassword123",
        },
    )
    assert res_unknown_email.status_code == 401

    # Both must return the identical generic error message
    assert res_wrong_pw.json()["detail"] == "Invalid email or password"
    assert res_unknown_email.json()["detail"] == "Invalid email or password"
    assert res_wrong_pw.json() == res_unknown_email.json()


def test_auth_me_scenarios(client):
    # 1. Register user
    reg = client.post(
        "/auth/register",
        json={
            "fullName": "Token Test User",
            "email": "tokentest@university.edu",
            "password": "ValidPassword123",
        },
    )
    token = reg.json()["accessToken"]
    user_id = reg.json()["user"]["id"]

    # Valid token
    me_valid = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_valid.status_code == 200
    assert me_valid.json()["id"] == user_id
    assert me_valid.json()["fullName"] == "Token Test User"
    assert me_valid.json()["email"] == "tokentest@university.edu"

    # Missing token
    me_missing = client.get("/auth/me")
    assert me_missing.status_code == 401

    # Garbage token
    me_garbage = client.get("/auth/me", headers={"Authorization": "Bearer this.is.garbage"})
    assert me_garbage.status_code == 401

    # Expired token
    expired_token = create_access_token(subject=user_id, expires_delta=timedelta(seconds=-30))
    me_expired = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert me_expired.status_code == 401


def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
