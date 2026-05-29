from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SPAPIReportTypeResponse(BaseModel):
    internal_report_type: str
    amazon_report_type: str
    display_name: str
    role_group: str
    source: str
    output_format: str
    parser_version: str
    normalizer_version: str
    status: str
    pii_risk: str
    notes: str


class SPAPISyncJobCreate(BaseModel):
    seller_account_id: int
    marketplace_id: int
    internal_report_type: str
    date_range_start: date
    date_range_end: date
    report_options: dict[str, Any] = Field(default_factory=dict)


class SPAPISyncJobResponse(BaseModel):
    id: int
    seller_account_id: int
    marketplace_id: int
    amazon_authorization_id: int
    import_job_id: int | None
    internal_report_type: str
    amazon_report_type: str
    date_range_start: date
    date_range_end: date
    status: str
    amazon_report_id: str | None
    amazon_report_document_id: str | None
    download_path: str | None
    error_code: str | None
    error_message: str | None
    requested_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
