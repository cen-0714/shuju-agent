from datetime import date
from pathlib import Path

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset
from app.models.normalized import NormalizedBusinessDaily, NormalizedOrderDaily
from app.models.settings import Marketplace, Organization, SellerAccount
from app.services.imports.spapi_ingestion import confirm_spapi_report_import


def test_confirm_spapi_report_import_persists_raw_and_normalized_rows(
    tmp_path: Path,
) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    fixture = Path(__file__).parent / "fixtures" / "sales_and_traffic_report.json"

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store",
            amazon_seller_id="A3FHEXAMPLEYWS",
        )
        marketplace = Marketplace(
            seller_account=seller,
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        )
        session.add(marketplace)
        session.flush()

        response = confirm_spapi_report_import(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            seller_account_id=seller.id,
            marketplace_id=marketplace.id,
            internal_report_type="business_sales_traffic",
            amazon_report_type="GET_SALES_AND_TRAFFIC_REPORT",
            date_range_start=date(2026, 5, 20),
            date_range_end=date(2026, 5, 20),
            original_filename="sales-and-traffic.json",
            file_bytes=fixture.read_bytes(),
        )
        session.commit()

        assert response.report_type == "business_report"
        assert session.query(ImportJob).one().source == "sp_api"
        assert session.query(RawDataset).one().source == "sp_api"
        row = session.query(NormalizedBusinessDaily).one()
        assert row.report_date == date(2026, 5, 20)
        assert row.sku == "SKU-1"
        assert row.asin == "B0TESTASIN"
        assert str(row.ordered_product_sales) == "125.50"
        assert row.units_ordered == 5


def test_confirm_spapi_orders_report_persists_tsv_with_tsv_suffix(
    tmp_path: Path,
) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    fixture = Path(__file__).parent / "fixtures" / "all_orders_report.tsv"

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="hrm",
            amazon_seller_id="A3M1UKV8VKJX6W",
        )
        marketplace = Marketplace(
            seller_account=seller,
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        )
        session.add(marketplace)
        session.flush()

        response = confirm_spapi_report_import(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            seller_account_id=seller.id,
            marketplace_id=marketplace.id,
            internal_report_type="orders_by_date",
            amazon_report_type="GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL",
            date_range_start=date(2026, 5, 28),
            date_range_end=date(2026, 5, 28),
            original_filename="doc-123.tsv",
            file_bytes=fixture.read_bytes(),
        )
        session.commit()

        assert response.report_type == "orders_report"
        assert response.raw_file_path.endswith(".tsv")
        rows = {
            (r.sku, r.currency): r for r in session.query(NormalizedOrderDaily).all()
        }
        # SKU-1 USD aggregated across 2 orders; Cancelled SKU-3 excluded
        assert ("SKU-1", "USD") in rows
        assert ("SKU-2", "CAD") in rows
        assert ("SKU-3", "USD") not in rows
        assert rows[("SKU-1", "USD")].units_ordered == 3
        assert str(rows[("SKU-1", "USD")].ordered_product_sales) == "30.00"
        assert rows[("SKU-1", "USD")].order_count == 2
