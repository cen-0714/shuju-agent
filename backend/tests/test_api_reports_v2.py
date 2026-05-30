from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.db import create_session_factory, create_sync_engine
from app.main import create_app
from app.models.base import Base


def make_client() -> TestClient:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def test_reports_api_flow(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    client = make_client()
    fixture = Path(__file__).parent / "fixtures" / "business_report.csv"
    seller = client.post(
        "/api/settings/seller-accounts",
        json={"display_name": "Store A", "amazon_seller_id": "SELLER-A"},
    ).json()
    marketplace = client.post(
        "/api/settings/marketplaces",
        json={
            "seller_account_id": seller["id"],
            "marketplace_id": "ATVPDKIKX0DER",
            "region": "americas",
            "country_code": "US",
            "timezone": "America/Los_Angeles",
            "currency_code": "USD",
        },
    ).json()
    with fixture.open("rb") as file:
        import_response = client.post(
            "/api/imports/confirm",
            data={
                "seller_account_id": str(seller["id"]),
                "marketplace_id": str(marketplace["id"]),
                "report_type": "business_report",
                "date_range_start": "2026-05-25",
                "date_range_end": "2026-05-25",
            },
            files={"file": ("business_report.csv", file, "text/csv")},
        )
    assert import_response.status_code == 200

    generate_response = client.post(
        "/api/reports/generate",
        json={
            "scope_type": "single_store",
            "report_kind": "single_day",
            "data_source": "business",
            "report_start_date": "2026-05-25",
            "report_end_date": "2026-05-25",
            "seller_account_id": seller["id"],
            "marketplace_id": marketplace["id"],
        },
    )
    assert generate_response.status_code == 200
    report_id = generate_response.json()["id"]

    list_response = client.get("/api/reports")
    detail_response = client.get(f"/api/reports/{report_id}")
    markdown_response = client.get(f"/api/reports/{report_id}/markdown")
    excel_response = client.get(f"/api/reports/{report_id}/excel")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert markdown_response.status_code == 200
    assert excel_response.status_code == 200
    assert "Daily Amazon Report" in markdown_response.text


def test_reports_generate_rejects_unknown_data_source() -> None:
    client = make_client()

    response = client.post(
        "/api/reports/generate",
        json={
            "scope_type": "all_stores",
            "report_kind": "date_range",
            "data_source": "typo",
            "report_start_date": "2026-05-25",
            "report_end_date": "2026-05-26",
        },
    )

    assert response.status_code == 422
