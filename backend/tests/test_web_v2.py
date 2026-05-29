from fastapi.testclient import TestClient

from app.main import create_app


def test_v2_pages_show_operational_controls() -> None:
    client = TestClient(create_app())

    pages = {
        "/": ["Recent Reports", "Stale Reports", "Recent Imports"],
        "/imports": ["Store", "Report type", "Preview", "Confirm Import", "Import History"],
        "/reports": ["All stores", "Single store", "Generate Report", "Download Excel"],
        "/settings": [
            "店铺档案",
            "卖家记号 / Merchant Token",
            "SP-API 自授权",
            "同一个卖家记号",
            "刷新令牌 Atzr",
            "可选：市场",
            "只测试 SP-API 授权可以先不填",
            "LLM Settings",
        ],
    }
    for path, expected_text in pages.items():
        response = client.get(path)
        assert response.status_code == 200
        for text in expected_text:
            assert text in response.text


def test_settings_page_uses_json_fetch_forms_instead_of_raw_api_navigation() -> None:
    client = TestClient(create_app())

    response = client.get("/settings")

    assert response.status_code == 200
    assert 'action="/api/settings/seller-accounts"' not in response.text
    assert 'action="/api/settings/marketplaces"' not in response.text
    assert 'url: "/api/settings/seller-accounts"' in response.text
    assert 'url: "/api/settings/marketplaces"' in response.text
    assert 'url: "/api/auth/amazon/self-authorizations"' in response.text
    assert "fetch(url" in response.text
