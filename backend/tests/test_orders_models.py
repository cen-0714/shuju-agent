from datetime import date
from decimal import Decimal

from app.core.db import create_session_factory, create_sync_engine
from app.domain.enums import DataSource, DataStatus, ImportJobStatus, ReportType
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset
from app.models.normalized import NormalizedOrderDaily
from app.models.settings import Marketplace, Organization, SellerAccount


def test_normalized_order_daily_roundtrip() -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org, display_name="hrm", amazon_seller_id="A3M1UKV8VKJX6W"
        )
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
            date_range_start=date(2026, 5, 28),
            date_range_end=date(2026, 5, 28),
            status=ImportJobStatus.SUCCEEDED.value,
            original_filename="orders.tsv",
        )
        dataset = RawDataset(
            import_job=job,
            seller_account=seller,
            marketplace=marketplace,
            source=DataSource.SP_API.value,
            report_type=ReportType.ORDERS_REPORT.value,
            date_range_start=date(2026, 5, 28),
            date_range_end=date(2026, 5, 28),
            schema_version="orders.v1",
            raw_file_path="raw/orders.tsv",
            raw_file_checksum="abc123",
            row_count=1,
            data_status=DataStatus.FINAL.value,
            data_version="sp_api:orders_report:2026-05-28:abc123",
        )
        row = NormalizedOrderDaily(
            raw_dataset=dataset,
            seller_account=seller,
            marketplace=marketplace,
            report_date=date(2026, 5, 28),
            sku="SKU-1",
            asin="B0AAA",
            product_name="Glass Globe",
            currency="CAD",
            units_ordered=3,
            ordered_product_sales=Decimal("119.97"),
            order_count=2,
        )
        session.add(row)
        session.commit()

        stored = session.get(NormalizedOrderDaily, row.id)
        assert stored is not None
        assert stored.currency == "CAD"
        assert stored.units_ordered == 3
        assert stored.ordered_product_sales == Decimal("119.97")
        assert stored.order_count == 2
        assert stored.seller_account_id == seller.id
