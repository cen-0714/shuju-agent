from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import DataSource, DataStatus, ReportType


class ImportPreviewRequest(BaseModel):
    seller_account_id: int
    marketplace_id: int
    report_type: ReportType
    date_range_start: date
    date_range_end: date


class ImportPreviewResponse(BaseModel):
    detected_schema_version: str
    row_count: int
    required_columns_present: bool
    missing_columns: list[str]
    sample_rows: list[dict[str, str]]
    data_status: DataStatus


class ImportConfirmResponse(BaseModel):
    import_job_id: int
    raw_dataset_id: int
    seller_account_id: int
    marketplace_id: int
    report_type: ReportType
    status: str
    original_filename: str
    raw_file_path: str
    raw_file_checksum: str
    row_count: int
    normalized_row_count: int
    data_status: DataStatus


class ImportJobResponse(BaseModel):
    id: int
    seller_account_id: int
    marketplace_id: int
    report_type: str
    date_range_start: date
    date_range_end: date
    status: str
    original_filename: str | None
    error_code: str | None
    error_message: str | None
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class RawDatasetEnvelopeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seller_account_id: int
    marketplace_id: int
    region: str
    source: DataSource
    report_type: ReportType
    date_range_start: date
    date_range_end: date
    schema_version: str
    raw_file_path: str
    raw_file_checksum: str
    row_count: int
    data_status: DataStatus
    data_version: str
    source_generated_at: datetime | None
