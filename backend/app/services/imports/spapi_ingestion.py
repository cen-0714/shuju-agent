from datetime import date

from sqlalchemy.orm import Session

from app.core.storage import LocalStorageBackend
from app.domain.enums import DataSource, ReportType
from app.schemas.imports import ImportConfirmResponse
from app.services.imports.persistence import persist_imported_report


class UnsupportedSPAPIReportTypeError(Exception):
    pass


def confirm_spapi_report_import(
    *,
    session: Session,
    storage: LocalStorageBackend,
    seller_account_id: int,
    marketplace_id: int,
    internal_report_type: str,
    amazon_report_type: str,
    date_range_start: date,
    date_range_end: date,
    original_filename: str,
    file_bytes: bytes,
) -> ImportConfirmResponse:
    if internal_report_type != "business_sales_traffic":
        raise UnsupportedSPAPIReportTypeError(
            f"Unsupported SP-API report type: {internal_report_type}"
        )
    if amazon_report_type != "GET_SALES_AND_TRAFFIC_REPORT":
        raise UnsupportedSPAPIReportTypeError(
            f"Unsupported Amazon report type: {amazon_report_type}"
        )

    return persist_imported_report(
        session=session,
        storage=storage,
        seller_account_id=seller_account_id,
        marketplace_id=marketplace_id,
        source=DataSource.SP_API,
        report_type=ReportType.BUSINESS_REPORT,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        original_filename=original_filename,
        file_bytes=file_bytes,
    )
