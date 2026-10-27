import pytest
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("API_KEY", "")
    get_settings.cache_clear()
    return TestClient(app)


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_jobs_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"][0]["id"] == "demo_pipeline"


def test_catalog_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/catalog")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["models"]) == 4
    assert "gmv" in data["metrics"]


def test_api_key_required_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "secret")
    get_settings.cache_clear()
    client = TestClient(app)
    assert client.get("/api/v1/jobs").status_code == 401
    assert client.get("/api/v1/jobs", headers={"X-API-Key": "secret"}).status_code == 200
    get_settings.cache_clear()
