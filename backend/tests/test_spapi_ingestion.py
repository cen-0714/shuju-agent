from datetime import date
from pathlib import Path

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset
from app.models.normalized import NormalizedBusinessDaily
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
