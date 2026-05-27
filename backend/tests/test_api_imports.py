from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_import_preview_endpoint_accepts_csv() -> None:
    client = TestClient(create_app())
    fixture = Path(__file__).parent / "fixtures" / "business_report.csv"

    with fixture.open("rb") as file:
        response = client.post(
            "/api/imports/preview",
            data={
                "report_type": "business_report",
                "date_range_start": "2026-05-25",
                "date_range_end": "2026-05-25",
            },
            files={"file": ("business_report.csv", file, "text/csv")},
        )

    assert response.status_code == 200
    assert response.json()["detected_schema_version"] == "business_report.v1"
