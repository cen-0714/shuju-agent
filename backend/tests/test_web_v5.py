from fastapi.testclient import TestClient

from app.main import create_app


def test_spapi_sync_page_is_available_and_uses_store_options() -> None:
    client = TestClient(create_app())

    response = client.get("/spapi-sync")

    assert response.status_code == 200
    assert "SP-API Sync" in response.text
    assert "/api/settings/store-options" in response.text
    assert "/api/spapi/report-types" in response.text
    assert "/api/spapi/sync-jobs" in response.text


def test_import_and_report_pages_no_longer_show_numeric_store_inputs() -> None:
    client = TestClient(create_app())

    imports = client.get("/imports").text
    reports = client.get("/reports").text

    assert 'name="seller_account_id" inputmode="numeric"' not in imports
    assert 'name="marketplace_id" inputmode="numeric"' not in imports
    assert 'name="seller_account_id" inputmode="numeric"' not in reports
    assert 'name="marketplace_id" inputmode="numeric"' not in reports
    assert "store-options" in imports
    assert "store-options" in reports
