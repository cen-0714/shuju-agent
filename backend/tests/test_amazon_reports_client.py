from datetime import date

import httpx

from app.services.amazon.reports_client import AmazonReportsClient


def test_reports_client_creates_report() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/reports"
        assert request.headers["x-amz-access-token"] == "access-token"
        payload = request.read().decode("utf-8")
        assert "GET_SALES_AND_TRAFFIC_REPORT" in payload
        assert "ATVPDKIKX0DER" in payload
        return httpx.Response(202, json={"reportId": "report-1"})

    client = AmazonReportsClient(
        base_url="https://sellingpartnerapi-na.amazon.com",
        transport=httpx.MockTransport(handler),
    )

    report_id = client.create_report(
        access_token="access-token",
        amazon_report_type="GET_SALES_AND_TRAFFIC_REPORT",
        marketplace_ids=["ATVPDKIKX0DER"],
        date_range_start=date(2026, 5, 20),
        date_range_end=date(2026, 5, 20),
        report_options={"dateGranularity": "DAY", "asinGranularity": "SKU"},
    )

    assert report_id == "report-1"


def test_reports_client_maps_403_to_permission_denied() -> None:
    client = AmazonReportsClient(
        base_url="https://sellingpartnerapi-na.amazon.com",
        transport=httpx.MockTransport(lambda _request: httpx.Response(403, text="denied")),
    )

    try:
        client.get_report(access_token="access-token", report_id="report-1")
    except PermissionError as exc:
        assert "permission denied" in str(exc).lower()
    else:
        raise AssertionError("Expected PermissionError")
