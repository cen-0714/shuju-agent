from fastapi.testclient import TestClient

from app.main import create_app


def test_report_types_endpoint_returns_only_enabled_types() -> None:
    client = TestClient(create_app())

    response = client.get("/api/spapi/report-types")

    assert response.status_code == 200
    payload = response.json()
    assert [item["internal_report_type"] for item in payload] == ["business_sales_traffic"]
    assert "open_listings" not in response.text
