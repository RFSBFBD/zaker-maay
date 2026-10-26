from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_preflight_allows_a_configured_frontend_origin() -> None:
    origin = get_settings().cors_origins[0]
    response = TestClient(app).options(
        "/api/v1/subjects",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_preflight_rejects_an_unconfigured_frontend_origin() -> None:
    response = TestClient(app).options(
        "/api/v1/subjects",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 400
