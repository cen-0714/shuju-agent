from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.errors import UnsupportedFileTypeError


@dataclass(frozen=True)
class ParsedReportFile:
    headers: list[str]
    rows: list[dict[str, str]]
    row_count: int
    sample_rows: list[dict[str, str]]


def parse_report_file(path: Path) -> ParsedReportFile:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, dtype=str).fillna("")
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype=str).fillna("")
    else:
        raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")

    rows = [
        {str(key): str(value) for key, value in row.items()}
        for row in frame.to_dict("records")
    ]
    return ParsedReportFile(
        headers=[str(column) for column in frame.columns],
        rows=rows,
        row_count=len(rows),
        sample_rows=rows[:5],
    )
