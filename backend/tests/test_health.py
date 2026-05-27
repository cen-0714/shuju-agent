from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_internal_pages_render() -> None:
    client = TestClient(create_app())

    for path in ["/", "/imports", "/reports", "/settings"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "Amazon Daily Copilot" in response.text
