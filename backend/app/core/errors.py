class AppError(Exception):
    code = "app_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedFileTypeError(AppError):
    code = "unsupported_file_type"


class UnknownSchemaError(AppError):
    code = "unknown_schema"


class MissingRequiredColumnsError(AppError):
    code = "missing_required_columns"

    def __init__(self, missing_columns: list[str]) -> None:
        self.missing_columns = missing_columns
        super().__init__(f"Missing required columns: {', '.join(missing_columns)}")
