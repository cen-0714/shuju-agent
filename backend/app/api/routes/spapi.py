from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.spapi import SPAPIReportTypeResponse, SPAPISyncJobCreate, SPAPISyncJobResponse
from app.services.amazon.report_types import get_enabled_report_types
from app.services.amazon.sync_jobs import SPAPISyncJobError, create_sync_job, list_sync_jobs

router = APIRouter(prefix="/spapi", tags=["spapi"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/report-types", response_model=list[SPAPIReportTypeResponse])
def report_types() -> list[SPAPIReportTypeResponse]:
    return [
        SPAPIReportTypeResponse(**report_type.__dict__)
        for report_type in get_enabled_report_types()
    ]


@router.get("/sync-jobs", response_model=list[SPAPISyncJobResponse])
def get_sync_jobs(session: SessionDep) -> list[SPAPISyncJobResponse]:
    return list_sync_jobs(session)


@router.post("/sync-jobs", response_model=SPAPISyncJobResponse)
def post_sync_job(payload: SPAPISyncJobCreate, session: SessionDep) -> SPAPISyncJobResponse:
    try:
        sync_job = create_sync_job(
            session=session,
            seller_account_id=payload.seller_account_id,
            marketplace_id=payload.marketplace_id,
            internal_report_type=payload.internal_report_type,
            date_range_start=payload.date_range_start,
            date_range_end=payload.date_range_end,
            report_options=payload.report_options,
        )
    except SPAPISyncJobError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return sync_job
