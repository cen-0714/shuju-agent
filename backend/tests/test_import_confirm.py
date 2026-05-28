from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.domain.enums import ReportType
from app.models.base import Base
from app.models.imports import RawDataset, RawReportRow
from app.models.normalized import (
    NormalizedAdsSearchTermDaily,
    NormalizedBusinessDaily,
    NormalizedInventoryDaily,
)
from app.models.settings import Marketplace, Organization, SellerAccount
from app.services.imports.persistence import confirm_manual_import


def test_confirm_business_report_persists_raw_and_normalized_rows(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    fixture = Path(__file__).parent / "fixtures" / "business_report.csv"

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="Store A",
            amazon_seller_id="SELLER-A",
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

        response = confirm_manual_import(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            seller_account_id=seller.id,
            marketplace_id=marketplace.id,
            report_type=ReportType.BUSINESS_REPORT,
            date_range_start=date(2026, 5, 25),
            date_range_end=date(2026, 5, 25),
            original_filename="business_report.csv",
            file_bytes=fixture.read_bytes(),
        )
        session.commit()

        assert response.status == "succeeded"
        assert response.row_count == 1
        assert response.original_filename == "business_report.csv"
        assert (tmp_path / response.raw_file_path).exists()
        assert session.scalar(select(func.count()).select_from(RawDataset)) == 1
        assert session.scalar(select(func.count()).select_from(RawReportRow)) == 1
        assert session.scalar(select(func.count()).select_from(NormalizedBusinessDaily)) == 1


def test_confirm_inventory_report_persists_inventory_rows(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    fixture = Path(__file__).parent / "fixtures" / "inventory_report.csv"

    with session_factory() as session:
        seller, marketplace = _create_store(session)

        response = confirm_manual_import(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            seller_account_id=seller.id,
            marketplace_id=marketplace.id,
            report_type=ReportType.INVENTORY_REPORT,
            date_range_start=date(2026, 5, 25),
            date_range_end=date(2026, 5, 25),
            original_filename="inventory_report.csv",
            file_bytes=fixture.read_bytes(),
        )
        session.commit()

        assert response.row_count == 1
        assert session.scalar(select(func.count()).select_from(RawDataset)) == 1
        assert session.scalar(select(func.count()).select_from(RawReportRow)) == 1
        assert session.scalar(select(func.count()).select_from(NormalizedInventoryDaily)) == 1


def test_confirm_ads_search_term_report_persists_ads_rows(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    fixture = Path(__file__).parent / "fixtures" / "ads_search_term_report.csv"

    with session_factory() as session:
        seller, marketplace = _create_store(session)

        response = confirm_manual_import(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            seller_account_id=seller.id,
            marketplace_id=marketplace.id,
            report_type=ReportType.ADS_SEARCH_TERM_REPORT,
            date_range_start=date(2026, 5, 25),
            date_range_end=date(2026, 5, 25),
            original_filename="ads_search_term_report.csv",
            file_bytes=fixture.read_bytes(),
        )
        session.commit()

        assert response.row_count == 1
        assert session.scalar(select(func.count()).select_from(RawDataset)) == 1
        assert session.scalar(select(func.count()).select_from(RawReportRow)) == 1
        assert session.scalar(select(func.count()).select_from(NormalizedAdsSearchTermDaily)) == 1


def _create_store(session):
    org = Organization(name="Internal Team", slug="internal")
    seller = SellerAccount(
        organization=org,
        display_name="Store A",
        amazon_seller_id="SELLER-A",
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
    return seller, marketplace
