import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import LocalStorageBackend
from app.core.time import classify_data_status
from app.domain.enums import DataSource, ImportJobStatus, ReportType
from app.models.imports import ImportJob, RawDataset, RawReportRow
from app.models.settings import Marketplace, SellerAccount
from app.schemas.imports import ImportConfirmResponse
from app.services.imports.parser import parse_report_file
from app.services.imports.schema_registry import detect_schema
from app.services.imports.validator import validate_required_columns
from app.services.normalization.persistence import persist_normalized_rows


def confirm_manual_import(
    *,
    session: Session,
    storage: LocalStorageBackend,
    seller_account_id: int,
    marketplace_id: int,
    report_type: ReportType,
    date_range_start: date,
    date_range_end: date,
    original_filename: str,
    file_bytes: bytes,
) -> ImportConfirmResponse:
    _ensure_store_exists(session, seller_account_id, marketplace_id)
    stored_file = storage.save_upload(
        category="raw",
        filename=original_filename,
        content=file_bytes,
    )
    parsed = parse_report_file(stored_file.absolute_path)
    schema = detect_schema(report_type, parsed.headers)
    validate_required_columns(schema, parsed.headers)

    duplicate = session.scalar(
        select(RawDataset.id).where(
            RawDataset.seller_account_id == seller_account_id,
            RawDataset.marketplace_id == marketplace_id,
            RawDataset.report_type == report_type.value,
            RawDataset.raw_file_checksum == stored_file.checksum,
        )
    )
    if duplicate is not None:
        storage.delete_file(stored_file.relative_path)
        raise ValueError("duplicate import file")

    data_status = classify_data_status(date_range_end)
    job = ImportJob(
        seller_account_id=seller_account_id,
        marketplace_id=marketplace_id,
        source=DataSource.MANUAL_FILE.value,
        report_type=report_type.value,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        status=ImportJobStatus.SUCCEEDED.value,
        original_filename=Path(original_filename).name or "upload.dat",
    )
    dataset = RawDataset(
        import_job=job,
        seller_account_id=seller_account_id,
        marketplace_id=marketplace_id,
        source=DataSource.MANUAL_FILE.value,
        report_type=report_type.value,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        schema_version=schema.version,
        raw_file_path=stored_file.relative_path,
        raw_file_checksum=stored_file.checksum,
        row_count=parsed.row_count,
        data_status=data_status.value,
        data_version=f"{report_type.value}:{date_range_end.isoformat()}:{stored_file.checksum[:12]}",
    )
    session.add(dataset)
    session.flush()

    for index, row in enumerate(parsed.rows, start=1):
        session.add(
            RawReportRow(
                raw_dataset=dataset,
                row_number=index,
                row_json=json.dumps(row, ensure_ascii=False),
            )
        )
    normalized_row_count = persist_normalized_rows(session, dataset, parsed.rows)
    session.flush()

    return ImportConfirmResponse(
        import_job_id=job.id,
        raw_dataset_id=dataset.id,
        seller_account_id=seller_account_id,
        marketplace_id=marketplace_id,
        report_type=report_type,
        status=job.status,
        original_filename=job.original_filename or original_filename,
        raw_file_path=dataset.raw_file_path,
        raw_file_checksum=dataset.raw_file_checksum,
        row_count=dataset.row_count,
        normalized_row_count=normalized_row_count,
        data_status=data_status,
    )


def _ensure_store_exists(session: Session, seller_account_id: int, marketplace_id: int) -> None:
    seller_account = session.get(SellerAccount, seller_account_id)
    marketplace = session.get(Marketplace, marketplace_id)
    if seller_account is None:
        raise ValueError("seller account not found")
    if marketplace is None or marketplace.seller_account_id != seller_account_id:
        raise ValueError("marketplace not found")
