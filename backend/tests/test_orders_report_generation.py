import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.domain.enums import DataSource, ReportKind, ReportScopeType, ReportType
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset
from app.models.normalized import NormalizedOrderDaily
from app.models.settings import Marketplace, Organization, SellerAccount
from app.schemas.reports import GenerateReportRequest
from app.services.reports.generator import generate_report


def _seed_store(session) -> tuple[SellerAccount, Marketplace, RawDataset]:
    org = Organization(name="Internal Team", slug="internal")
    seller = SellerAccount(organization=org, display_name="hrm", amazon_seller_id="A3M1UKV8VKJX6W")
    marketplace = Marketplace(
        seller_account=seller,
        marketplace_id="ATVPDKIKX0DER",
        region="americas",
        country_code="US",
        timezone="America/Los_Angeles",
        currency_code="USD",
    )
    job = ImportJob(
        seller_account=seller,
        marketplace=marketplace,
        source=DataSource.SP_API.value,
        report_type=ReportType.ORDERS_REPORT.value,
        date_range_start=date(2026, 5, 1),
        date_range_end=date(2026, 5, 31),
        status="succeeded",
        original_filename="orders.tsv",
    )
    dataset = RawDataset(
        import_job=job,
        seller_account=seller,
        marketplace=marketplace,
        source=DataSource.SP_API.value,
        report_type=ReportType.ORDERS_REPORT.value,
        date_range_start=date(2026, 5, 1),
        date_range_end=date(2026, 5, 31),
        schema_version="orders.v1",
        raw_file_path="raw/orders.tsv",
        raw_file_checksum="chk-orders",
        row_count=4,
        data_status="final",
        data_version="sp_api:orders_report:2026-05-31:chk-orders",
    )
    session.add(dataset)
    session.flush()
    return seller, marketplace, dataset


def _order(dataset, seller, marketplace, *, day, sku, currency, units, sales, orders):
    return NormalizedOrderDaily(
        raw_dataset=dataset,
        seller_account=seller,
        marketplace=marketplace,
        report_date=day,
        sku=sku,
        asin=f"B0{sku}",
        product_name=f"Product {sku}",
        currency=currency,
        units_ordered=units,
        ordered_product_sales=sales,
        order_count=orders,
    )


def test_orders_date_range_report_builds_trend_and_sku_performance(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        seller, marketplace, dataset = _seed_store(session)
        # Two days in same ISO week + month, two currencies, two SKUs
        session.add_all(
            [
                _order(
                    dataset, seller, marketplace,
                    day=date(2026, 5, 4), sku="SKU-1", currency="USD",
                    units=2, sales=Decimal("20.00"), orders=2,
                ),
                _order(
                    dataset, seller, marketplace,
                    day=date(2026, 5, 5), sku="SKU-1", currency="USD",
                    units=3, sales=Decimal("30.00"), orders=3,
                ),
                _order(
                    dataset, seller, marketplace,
                    day=date(2026, 5, 5), sku="SKU-2", currency="CAD",
                    units=1, sales=Decimal("40.00"), orders=1,
                ),
            ]
        )
        session.flush()

        report = generate_report(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            request=GenerateReportRequest(
                scope_type=ReportScopeType.SINGLE_STORE,
                report_kind=ReportKind.DATE_RANGE,
                report_start_date=date(2026, 5, 1),
                report_end_date=date(2026, 5, 31),
                data_source="orders",
                seller_account_id=seller.id,
                marketplace_id=marketplace.id,
            ),
        )
        session.commit()

        body = json.loads(report.report_json)
        assert body["data_source"] == "orders"
        assert "ordered_product_sales" not in body["totals"]
        totals_by_currency = {
            item["currency"]: item for item in body["totals_by_currency"]
        }
        assert totals_by_currency["USD"]["ordered_product_sales"] == "50.00"
        assert totals_by_currency["USD"]["units_ordered"] == 5
        assert totals_by_currency["CAD"]["ordered_product_sales"] == "40.00"
        assert totals_by_currency["CAD"]["units_ordered"] == 1

        # store summaries split by currency
        currencies = {s["currency"] for s in body["store_summaries"]}
        assert currencies == {"USD", "CAD"}

        # trend has day, week, month buckets
        labels = {p["period_label"] for p in body["trend"]}
        assert any(label.startswith("D:") for label in labels)
        assert any(label.startswith("W:") for label in labels)
        assert any(label.startswith("M:") for label in labels)

        # USD month total = 50.00 (20 + 30), units 5
        month_usd = next(
            p for p in body["trend"]
            if p["period_label"].startswith("M:") and p["currency"] == "USD"
        )
        assert month_usd["ordered_product_sales"] == "50.00"
        assert month_usd["units_ordered"] == 5
        assert month_usd["order_count"] == 5

        # SKU performance sorted by sales desc; SKU-2 CAD 40 > SKU-1 USD 50? no: 50 > 40
        skus = [(s["sku"], s["currency"]) for s in body["sku_performance"]]
        assert skus[0] == ("SKU-1", "USD")


def test_orders_report_fails_without_data(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            generate_report(
                session=session,
                storage=LocalStorageBackend(tmp_path),
                request=GenerateReportRequest(
                    scope_type=ReportScopeType.ALL_STORES,
                    report_kind=ReportKind.DATE_RANGE,
                    report_start_date=date(2026, 5, 1),
                    report_end_date=date(2026, 5, 31),
                    data_source="orders",
                ),
            )
        except ValueError as exc:
            assert "no order data" in str(exc)
        else:
            raise AssertionError("expected failure without order data")
