from app.core.errors import MissingRequiredColumnsError
from app.services.imports.schema_registry import ReportSchema


def validate_required_columns(schema: ReportSchema, headers: list[str]) -> None:
    missing = sorted(schema.required_columns - set(headers))
    if missing:
        raise MissingRequiredColumnsError(missing)
