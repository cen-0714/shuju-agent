from fastapi.testclient import TestClient

from app.main import create_app


def test_default_marketplaces_endpoint_returns_americas_marketplaces() -> None:
    client = TestClient(create_app())

    response = client.get("/api/settings/default-marketplaces")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["marketplace_id"] == "ATVPDKIKX0DER"
    assert payload[0]["region"] == "americas"
