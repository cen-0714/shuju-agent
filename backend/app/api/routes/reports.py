import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.config import Settings
from app.core.storage import create_storage_backend
from app.models.reports import DailyReport
from app.schemas.reports import DailyReportResponse, GenerateReportRequest
from app.services.reports.generator import generate_report

router = APIRouter(prefix="/reports", tags=["reports"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/generate", response_model=DailyReportResponse)
def post_generate_report(
    payload: GenerateReportRequest,
    session: SessionDep,
) -> DailyReport:
    storage = create_storage_backend(Settings().STORAGE_ROOT)
    try:
        report = generate_report(session=session, storage=storage, request=payload)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return report


@router.get("", response_model=list[DailyReportResponse])
def list_reports(session: SessionDep) -> list[DailyReport]:
    return list(session.scalars(select(DailyReport).order_by(DailyReport.created_at.desc())))


@router.get("/{report_id}", response_model=DailyReportResponse)
def get_report(report_id: int, session: SessionDep) -> DailyReport:
    return _get_report_or_404(session, report_id)


@router.get("/{report_id}/markdown", response_class=PlainTextResponse)
def get_report_markdown(report_id: int, session: SessionDep) -> str:
    return _get_report_or_404(session, report_id).markdown


@router.get("/{report_id}/excel")
def get_report_excel(report_id: int, session: SessionDep) -> FileResponse:
    report = _get_report_or_404(session, report_id)
    if not report.excel_path:
        raise HTTPException(status_code=404, detail="excel report not found")
    storage = create_storage_backend(Settings().STORAGE_ROOT)
    path = storage.resolve_path(report.excel_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="excel report file not found")
    return FileResponse(
        path,
        filename=f"amazon-report-{report.id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/{report_id}/regenerate", response_model=DailyReportResponse)
def regenerate_report(report_id: int, session: SessionDep) -> DailyReport:
    existing = _get_report_or_404(session, report_id)
    try:
        stored_document = json.loads(existing.report_json)
    except (ValueError, TypeError):
        stored_document = {}
    payload = GenerateReportRequest(
        scope_type=existing.scope_type,
        report_kind=existing.report_kind,
        report_start_date=existing.report_start_date,
        report_end_date=existing.report_end_date,
        data_source=stored_document.get("data_source", "business"),
        seller_account_id=existing.seller_account_id,
        marketplace_id=existing.marketplace_id,
    )
    storage = create_storage_backend(Settings().STORAGE_ROOT)
    try:
        report = generate_report(session=session, storage=storage, request=payload)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return report


def _get_report_or_404(session: Session, report_id: int) -> DailyReport:
    report = session.get(DailyReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report
