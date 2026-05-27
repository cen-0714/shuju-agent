from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.domain.enums import ReportType
from app.schemas.imports import ImportPreviewResponse
from app.services.imports.orchestrator import preview_manual_import

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    report_type: Annotated[ReportType, Form()],
    date_range_start: Annotated[date, Form()],
    date_range_end: Annotated[date, Form()],
    file: Annotated[UploadFile, File()],
) -> ImportPreviewResponse:
    suffix = Path(file.filename or "upload.csv").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    return preview_manual_import(
        file_path=tmp_path,
        report_type=report_type,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )
