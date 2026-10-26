from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_is_independent_of_provider_configuration() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_presence_without_values() -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"configured_unchecked", "not_configured"}
    assert set(body["services"]) == {"database", "supabase_auth", "cloudinary", "gemini"}
    assert "DATABASE_URL" not in response.text


def test_metadata_has_no_provider_configuration() -> None:
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    assert response.json()["api_version"] == "v1"
