from pathlib import Path

from app.services.imports.parser import parse_report_file


def test_parse_tsv_orders_file(tmp_path: Path) -> None:
    content = (
        "amazon-order-id\tpurchase-date\tsku\tasin\tproduct-name\tquantity\t"
        "currency\titem-price\torder-status\n"
        "702-1\t2026-05-29T23:15:45+00:00\tSKU-1\tB0AAA\tGlass Globe\t1\t"
        "CAD\t39.99\tShipped\n"
        "702-2\t2026-05-29T10:00:00+00:00\tSKU-2\tB0BBB\tWidget\t2\t"
        "USD\t10.00\tPending\n"
    )
    path = tmp_path / "orders.tsv"
    path.write_text(content, encoding="utf-8")

    parsed = parse_report_file(path)

    assert parsed.row_count == 2
    assert "purchase-date" in parsed.headers
    assert "currency" in parsed.headers
    assert parsed.rows[0]["sku"] == "SKU-1"
    assert parsed.rows[0]["currency"] == "CAD"
    assert parsed.rows[1]["item-price"] == "10.00"
