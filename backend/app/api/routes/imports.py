from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.config import Settings
from app.core.storage import create_storage_backend
from app.domain.enums import ReportType
from app.models.imports import ImportJob
from app.schemas.imports import ImportConfirmResponse, ImportJobResponse, ImportPreviewResponse
from app.services.imports.deletion import delete_import_job
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


@router.get("/jobs", response_model=list[ImportJobResponse])
def list_import_jobs(session: SessionDep) -> list[ImportJob]:
    return list(session.scalars(select(ImportJob).order_by(ImportJob.created_at.desc())))


@router.get("/jobs/{import_job_id}", response_model=ImportJobResponse)
def get_import_job(import_job_id: int, session: SessionDep) -> ImportJob:
    import_job = session.get(ImportJob, import_job_id)
    if import_job is None:
        raise HTTPException(status_code=404, detail="import job not found")
    return import_job


@router.delete("/jobs/{import_job_id}", response_model=ImportJobResponse)
def delete_import(import_job_id: int, session: SessionDep) -> ImportJob:
    storage = create_storage_backend(Settings().STORAGE_ROOT)
    try:
        import_job = delete_import_job(session, storage, import_job_id)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return import_job
