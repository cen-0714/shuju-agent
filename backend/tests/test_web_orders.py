from fastapi.testclient import TestClient

from app.main import create_app


def test_reports_page_has_data_source_selector() -> None:
    client = TestClient(create_app())

    reports = client.get("/reports").text

    assert 'name="data_source"' in reports
    assert 'value="orders"' in reports
    assert 'value="business"' in reports


def test_report_types_endpoint_lists_orders_by_date() -> None:
    client = TestClient(create_app())

    response = client.get("/api/spapi/report-types")

    assert response.status_code == 200
    internal_types = {item["internal_report_type"] for item in response.json()}
    assert "orders_by_date" in internal_types
