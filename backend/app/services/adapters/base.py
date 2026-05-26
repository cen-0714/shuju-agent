from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.enums import DataSource, DataStatus, ReportType


@dataclass(frozen=True)
class RawDatasetEnvelope:
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


class DataSourceAdapter(ABC):
    source: DataSource

    @abstractmethod
    def build_envelope(self, *args: object, **kwargs: object) -> RawDatasetEnvelope:
        raise NotImplementedError
