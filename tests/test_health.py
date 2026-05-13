"""Tests for the service health endpoint."""

from app.main import app
from fastapi.testclient import TestClient


def test_health_returns_ok() -> None:
    """The health endpoint should confirm the API is alive."""

    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "business-insight-agent",
    }
