from sqlalchemy import text

from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.domain.enums import DataSource, DataStatus, Region, ReportType


def test_settings_defaults_to_local_storage() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")

    assert settings.APP_ENV == "local"
    assert settings.STORAGE_ROOT == "storage"


def test_domain_enums_have_required_values() -> None:
    assert Region.AMERICAS.value == "americas"
    assert DataSource.MANUAL_FILE.value == "manual_file"
    assert ReportType.BUSINESS_REPORT.value == "business_report"
    assert DataStatus.PRELIMINARY.value == "preliminary"


def test_session_factory_executes_sql() -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        value = session.execute(text("select 1")).scalar_one()

    assert value == 1


def test_orm_can_create_core_records() -> None:
    from datetime import date

    from app.models.base import Base
    from app.models.imports import ImportJob, RawDataset
    from app.models.settings import Marketplace, Organization, SellerAccount

    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store A",
            amazon_seller_id="A1SELLER",
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
            source="manual_file",
            report_type="business_report",
            date_range_start=date(2026, 5, 25),
            date_range_end=date(2026, 5, 25),
            status="pending",
        )
        dataset = RawDataset(
            import_job=job,
            seller_account=seller,
            marketplace=marketplace,
            source="manual_file",
            report_type="business_report",
            date_range_start=date(2026, 5, 25),
            date_range_end=date(2026, 5, 25),
            schema_version="business_report.v1",
            raw_file_path="storage/raw/business.csv",
            raw_file_checksum="abc123",
            row_count=1,
            data_status="stable",
            data_version="2026-05-25-1",
        )
        session.add(dataset)
        session.commit()

        assert dataset.id is not None
        assert dataset.seller_account.display_name == "US Store A"
