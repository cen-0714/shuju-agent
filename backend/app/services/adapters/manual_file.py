from datetime import date
from hashlib import sha256
from pathlib import Path

from app.domain.enums import DataSource, DataStatus, ReportType
from app.services.adapters.base import DataSourceAdapter, RawDatasetEnvelope


class ManualFileAdapter(DataSourceAdapter):
    source = DataSource.MANUAL_FILE

    def __init__(self, storage_root: Path | str) -> None:
        self.storage_root = Path(storage_root)

    def build_envelope(
        self,
        *,
        source_file: Path,
        seller_account_id: int,
        marketplace_id: int,
        region: str,
        report_type: ReportType,
        date_range_start: date,
        date_range_end: date,
        schema_version: str,
        row_count: int,
        data_status: DataStatus,
    ) -> RawDatasetEnvelope:
        checksum = self._checksum(source_file)
        relative_path = f"raw/{seller_account_id}/{marketplace_id}/{checksum}{source_file.suffix}"
        data_version = f"{date_range_end.isoformat()}-{checksum[:8]}"
        return RawDatasetEnvelope(
            seller_account_id=seller_account_id,
            marketplace_id=marketplace_id,
            region=region,
            source=self.source,
            report_type=report_type,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            schema_version=schema_version,
            raw_file_path=relative_path,
            raw_file_checksum=checksum,
            row_count=row_count,
            data_status=data_status,
            data_version=data_version,
            source_generated_at=None,
        )

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = sha256()
        digest.update(path.read_bytes())
        return digest.hexdigest()
