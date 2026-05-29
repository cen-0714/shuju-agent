from fastapi.testclient import TestClient

from app.main import create_app


def test_v2_pages_show_operational_controls() -> None:
    client = TestClient(create_app())

    pages = {
        "/": ["Recent Reports", "Stale Reports", "Recent Imports"],
        "/imports": ["Store", "Report type", "Preview", "Confirm Import", "Import History"],
        "/reports": ["All stores", "Single store", "Generate Report", "Download Excel"],
        "/settings": [
            "Seller Accounts",
            "Marketplaces",
            "Amazon Self Authorization",
            "Refresh token",
            "LLM Settings",
        ],
    }
    for path, expected_text in pages.items():
        response = client.get(path)
        assert response.status_code == 200
        for text in expected_text:
            assert text in response.text
