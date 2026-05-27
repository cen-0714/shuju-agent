from datetime import date
from pathlib import Path

from app.core.errors import MissingRequiredColumnsError
from app.core.time import classify_data_status
from app.domain.enums import ReportType
from app.schemas.imports import ImportPreviewResponse
from app.services.imports.parser import parse_report_file
from app.services.imports.schema_registry import detect_schema
from app.services.imports.validator import validate_required_columns


def preview_manual_import(
    *,
    file_path: Path,
    report_type: ReportType,
    date_range_start: date,
    date_range_end: date,
) -> ImportPreviewResponse:
    parsed = parse_report_file(file_path)
    schema = detect_schema(report_type, parsed.headers)
    missing_columns: list[str] = []
    try:
        validate_required_columns(schema, parsed.headers)
    except MissingRequiredColumnsError as exc:
        missing_columns = exc.missing_columns

    return ImportPreviewResponse(
        detected_schema_version=schema.version,
        row_count=parsed.row_count,
        required_columns_present=not missing_columns,
        missing_columns=missing_columns,
        sample_rows=parsed.sample_rows,
        data_status=classify_data_status(date_range_end),
    )
