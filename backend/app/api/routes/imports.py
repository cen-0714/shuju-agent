from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.config import Settings
from app.core.storage import create_storage_backend
from app.domain.enums import ReportType
from app.schemas.imports import ImportConfirmResponse, ImportPreviewResponse
from app.services.imports.orchestrator import preview_manual_import
from app.services.imports.persistence import confirm_manual_import

router = APIRouter(prefix="/imports", tags=["imports"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    seller_account_id: Annotated[int, Form()],
    marketplace_id: Annotated[int, Form()],
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


@router.post("/confirm", response_model=ImportConfirmResponse)
async def confirm_import(
    seller_account_id: Annotated[int, Form()],
    marketplace_id: Annotated[int, Form()],
    report_type: Annotated[ReportType, Form()],
    date_range_start: Annotated[date, Form()],
    date_range_end: Annotated[date, Form()],
    file: Annotated[UploadFile, File()],
    session: SessionDep,
) -> ImportConfirmResponse:
    storage = create_storage_backend(Settings().STORAGE_ROOT)
    try:
        response = confirm_manual_import(
            session=session,
            storage=storage,
            seller_account_id=seller_account_id,
            marketplace_id=marketplace_id,
            report_type=report_type,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            original_filename=file.filename or "upload.dat",
            file_bytes=await file.read(),
        )
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return response
