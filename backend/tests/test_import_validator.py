from app.core.errors import MissingRequiredColumnsError
from app.domain.enums import ReportType
from app.services.imports.schema_registry import detect_schema
from app.services.imports.validator import validate_required_columns


def test_validate_required_columns_passes() -> None:
    schema = detect_schema(
        ReportType.BUSINESS_REPORT,
        ["Date", "Sessions", "Units Ordered", "Ordered Product Sales"],
    )

    validate_required_columns(
        schema,
        ["Date", "Sessions", "Units Ordered", "Ordered Product Sales"],
    )


def test_validate_required_columns_raises_with_missing_names() -> None:
    schema = detect_schema(
        ReportType.BUSINESS_REPORT,
        ["Date", "Sessions", "Units Ordered", "Ordered Product Sales"],
    )

    try:
        validate_required_columns(schema, ["Date", "Sessions"])
    except MissingRequiredColumnsError as exc:
        assert exc.missing_columns == ["Ordered Product Sales", "Units Ordered"]
    else:
        raise AssertionError("Expected MissingRequiredColumnsError")
