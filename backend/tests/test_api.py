import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_admin_login():
    """Verify Admin account can authenticate with configured credentials."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["email"] == settings.ADMIN_EMAIL

def test_login_invalid_credentials():
    """Verify that wrong password returns 401 Unauthorized."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": "completely_wrong_password"}
    )
    assert response.status_code == 401

def test_candidate_registration_and_flow():
    """Test candidate registration and subsequent login."""
    test_email = f"candidate_test_{int(pytest.importorskip('time').time())}@example.com"
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Candidate",
            "email": test_email,
            "password": "Password123!"
        }
    )
    assert reg_response.status_code == 201
    reg_data = reg_response.json()
    assert reg_data["email"] == test_email
    assert reg_data["role"] == "CANDIDATE"

    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": "Password123!"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Access candidate profile
    headers = {"Authorization": f"Bearer {token}"}
    profile_res = client.get("/api/v1/candidate/profile", headers=headers)
    assert profile_res.status_code == 200
    profile_data = profile_res.json()
    assert profile_data["email"] == test_email
    assert "profile_percentage" in profile_data

def test_technical_assessments_endpoint():
    """Verify seeded assessments are available."""
    response = client.get("/api/v1/assessments")
    assert response.status_code == 200
    assessments = response.json()
    assert len(assessments) >= 5
    techs = [a["technology"] for a in assessments]
    assert "Python" in techs
    assert "React" in techs

def test_admin_analytics_endpoint():
    """Verify admin platform analytics endpoint."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    analytics_res = client.get("/api/v1/admin/analytics", headers=headers)
    assert analytics_res.status_code == 200
    stats = analytics_res.json()
    assert "total_users" in stats
    assert stats["total_users"] >= 1
