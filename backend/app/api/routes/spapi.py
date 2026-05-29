from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.core.storage import create_storage_backend
from app.models.amazon import SPAPISyncJob
from app.schemas.spapi import SPAPIReportTypeResponse, SPAPISyncJobCreate, SPAPISyncJobResponse
from app.services.amazon.lwa import LWAClient
from app.services.amazon.report_types import get_enabled_report_types
from app.services.amazon.reports_client import AmazonReportsClient
from app.services.amazon.sync_jobs import (
    SPAPISyncJobError,
    create_sync_job,
    list_sync_jobs,
    refresh_sync_job,
    run_sync_job,
)
from app.services.security.tokens import TokenCipher

router = APIRouter(prefix="/spapi", tags=["spapi"])
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


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


@router.post("/sync-jobs/{sync_job_id}/run", response_model=SPAPISyncJobResponse)
def post_run_sync_job(
    sync_job_id: int,
    session: SessionDep,
    settings: SettingsDep,
) -> SPAPISyncJobResponse:
    sync_job = session.get(SPAPISyncJob, sync_job_id)
    if sync_job is None:
        raise HTTPException(status_code=404, detail="sync job not found")
    refresh_token = _decrypt_refresh_token(sync_job, settings)
    result = run_sync_job(
        session=session,
        sync_job_id=sync_job_id,
        refresh_token_plaintext=refresh_token,
        lwa_client=LWAClient(
            token_url=settings.AMAZON_LWA_TOKEN_URL,
            client_id=settings.AMAZON_LWA_CLIENT_ID or "",
            client_secret=settings.AMAZON_LWA_CLIENT_SECRET or "",
            timeout_seconds=settings.AMAZON_LWA_TIMEOUT_SECONDS,
        ),
        reports_client=AmazonReportsClient(
            base_url=settings.AMAZON_SPAPI_BASE_URL,
            timeout_seconds=settings.AMAZON_REPORTS_TIMEOUT_SECONDS,
        ),
    )
    session.commit()
    return result


@router.post("/sync-jobs/{sync_job_id}/refresh", response_model=SPAPISyncJobResponse)
def post_refresh_sync_job(
    sync_job_id: int,
    session: SessionDep,
    settings: SettingsDep,
) -> SPAPISyncJobResponse:
    sync_job = session.get(SPAPISyncJob, sync_job_id)
    if sync_job is None:
        raise HTTPException(status_code=404, detail="sync job not found")
    refresh_token = _decrypt_refresh_token(sync_job, settings)
    result = refresh_sync_job(
        session=session,
        storage=create_storage_backend(settings.STORAGE_ROOT),
        sync_job_id=sync_job_id,
        refresh_token_plaintext=refresh_token,
        lwa_client=LWAClient(
            token_url=settings.AMAZON_LWA_TOKEN_URL,
            client_id=settings.AMAZON_LWA_CLIENT_ID or "",
            client_secret=settings.AMAZON_LWA_CLIENT_SECRET or "",
            timeout_seconds=settings.AMAZON_LWA_TIMEOUT_SECONDS,
        ),
        reports_client=AmazonReportsClient(
            base_url=settings.AMAZON_SPAPI_BASE_URL,
            timeout_seconds=settings.AMAZON_REPORTS_TIMEOUT_SECONDS,
        ),
    )
    session.commit()
    return result


def _decrypt_refresh_token(sync_job: SPAPISyncJob, settings: Settings) -> str:
    try:
        return TokenCipher(settings.TOKEN_ENCRYPTION_KEY or "").decrypt(
            sync_job.amazon_authorization.refresh_token_encrypted
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Amazon refresh token decrypt failed") from exc
