"""Tests for the service health endpoint."""

from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_health_endpoint_reports_service_details() -> None:
    """The health endpoint exposes service availability and non-secret runtime metadata."""
    app = create_app(Settings(environment="test"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "test",
        "version": "0.1.0",
    }
