import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_returns_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok"}


def test_health_rejects_post(client):
    response = client.post("/api/health")

    assert response.status_code == 405


def test_unknown_route_returns_404(client):
    assert client.get("/api/missing").status_code == 404


def test_openapi_describes_health_response(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    health = schema["paths"]["/api/health"]["get"]
    assert health["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HealthResponse"
    }


def test_swagger_html_is_available(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SwaggerUIBundle" in response.text
