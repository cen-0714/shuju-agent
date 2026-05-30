import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.domain.enums import AmazonAuthorizationStatus, SPAPISyncJobErrorCode, SPAPISyncJobStatus
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
from app.models.settings import Marketplace, SellerAccount
from app.services.amazon.lwa import LWATokenExchangeError
from app.services.amazon.report_types import (
    ReportTypeDisabledError,
    get_report_type,
    require_enabled_report_type,
)
from app.services.amazon.reports_client import AmazonReportsRateLimitError
from app.services.imports.spapi_ingestion import confirm_spapi_report_import


class SPAPISyncJobError(Exception):
    pass


def create_sync_job(
    *,
    session: Session,
    seller_account_id: int,
    marketplace_id: int,
    internal_report_type: str,
    date_range_start: date,
    date_range_end: date,
    report_options: dict[str, object],
) -> SPAPISyncJob:
    seller = session.get(SellerAccount, seller_account_id)
    marketplace = session.get(Marketplace, marketplace_id)
    if seller is None:
        raise SPAPISyncJobError("seller account not found")
    if marketplace is None or marketplace.seller_account_id != seller.id:
        raise SPAPISyncJobError("marketplace not found")
    if date_range_start > date_range_end:
        raise SPAPISyncJobError("date_range_start cannot be after date_range_end")
    try:
        report_type = require_enabled_report_type(internal_report_type)
    except ReportTypeDisabledError as exc:
        raise SPAPISyncJobError(str(exc)) from exc

    authorization = session.scalar(
        select(AmazonAuthorization).where(
            AmazonAuthorization.seller_account_id == seller.id,
            AmazonAuthorization.status == AmazonAuthorizationStatus.ACTIVE.value,
        )
    )
    if authorization is None:
        raise SPAPISyncJobError("active Amazon authorization not found")

    if report_type.output_format == "json":
        normalized_options = {
            "dateGranularity": str(report_options.get("dateGranularity") or "DAY"),
            "asinGranularity": str(report_options.get("asinGranularity") or "SKU"),
        }
    else:
        normalized_options = {}
    sync_job = SPAPISyncJob(
        seller_account=seller,
        marketplace=marketplace,
        amazon_authorization=authorization,
        internal_report_type=report_type.internal_report_type,
        amazon_report_type=report_type.amazon_report_type,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        report_options_json=json.dumps(normalized_options, separators=(",", ":")),
        status=SPAPISyncJobStatus.DRAFT.value,
    )
    session.add(sync_job)
    session.flush()
    return sync_job


def list_sync_jobs(session: Session) -> list[SPAPISyncJob]:
    return list(session.scalars(select(SPAPISyncJob).order_by(SPAPISyncJob.created_at.desc())))


def run_sync_job(
    *,
    session: Session,
    sync_job_id: int,
    refresh_token_plaintext: str,
    lwa_client,
    reports_client,
) -> SPAPISyncJob:
    sync_job = _get_sync_job(session, sync_job_id)
    try:
        token = lwa_client.exchange_refresh_token(refresh_token=refresh_token_plaintext)
        report_options = json.loads(sync_job.report_options_json or "{}")
        sync_job.amazon_report_id = reports_client.create_report(
            access_token=token.access_token,
            amazon_report_type=sync_job.amazon_report_type,
            marketplace_ids=[sync_job.marketplace.marketplace_id],
            date_range_start=sync_job.date_range_start,
            date_range_end=sync_job.date_range_end,
            report_options=report_options,
        )
        sync_job.status = SPAPISyncJobStatus.REQUESTED.value
        sync_job.requested_at = utc_now()
        sync_job.error_code = None
        sync_job.error_message = None
    except LWATokenExchangeError as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.LWA_TOKEN_FAILED.value, str(exc))
    except PermissionError as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.PERMISSION_DENIED.value, str(exc))
    except AmazonReportsRateLimitError as exc:
        retry_after = f" retry-after={exc.retry_after}" if exc.retry_after else ""
        _mark_failed(sync_job, SPAPISyncJobErrorCode.RATE_LIMITED.value, f"{exc}{retry_after}")
    except Exception as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.UNEXPECTED_ERROR.value, str(exc))
    session.flush()
    return sync_job


def refresh_sync_job(
    *,
    session: Session,
    storage,
    sync_job_id: int,
    refresh_token_plaintext: str,
    lwa_client,
    reports_client,
    downloaded_content: bytes | None = None,
) -> SPAPISyncJob:
    sync_job = _get_sync_job(session, sync_job_id)
    if not sync_job.amazon_report_id:
        raise SPAPISyncJobError("sync job has no Amazon report id")

    try:
        token = lwa_client.exchange_refresh_token(refresh_token=refresh_token_plaintext)
        status = reports_client.get_report(
            access_token=token.access_token,
            report_id=sync_job.amazon_report_id,
        )
        if status.processing_status in {"IN_QUEUE", "IN_PROGRESS"}:
            sync_job.status = SPAPISyncJobStatus.PROCESSING.value
            session.flush()
            return sync_job
        if status.processing_status != "DONE" or not status.report_document_id:
            _mark_failed(
                sync_job,
                SPAPISyncJobErrorCode.AMAZON_REPORT_FAILED.value,
                f"Amazon report status: {status.processing_status}",
            )
            session.flush()
            return sync_job

        document = reports_client.get_report_document(
            access_token=token.access_token,
            report_document_id=status.report_document_id,
        )
        sync_job.amazon_report_document_id = document.report_document_id
        content = downloaded_content
        if content is None:
            from app.services.amazon.report_downloads import download_report_document

            content = download_report_document(
                url=document.url,
                report_document_id=document.report_document_id,
                compression_algorithm=document.compression_algorithm,
            ).content
        file_suffix = _report_file_suffix(sync_job.internal_report_type)
        response = confirm_spapi_report_import(
            session=session,
            storage=storage,
            seller_account_id=sync_job.seller_account_id,
            marketplace_id=sync_job.marketplace_id,
            internal_report_type=sync_job.internal_report_type,
            amazon_report_type=sync_job.amazon_report_type,
            date_range_start=sync_job.date_range_start,
            date_range_end=sync_job.date_range_end,
            original_filename=f"{document.report_document_id}.{file_suffix}",
            file_bytes=content,
        )
        sync_job.import_job_id = response.import_job_id
        sync_job.download_path = response.raw_file_path
        sync_job.status = SPAPISyncJobStatus.IMPORTED.value
        sync_job.completed_at = utc_now()
        sync_job.error_code = None
        sync_job.error_message = None
    except LWATokenExchangeError as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.LWA_TOKEN_FAILED.value, str(exc))
    except PermissionError as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.PERMISSION_DENIED.value, str(exc))
    except AmazonReportsRateLimitError as exc:
        retry_after = f" retry-after={exc.retry_after}" if exc.retry_after else ""
        _mark_failed(sync_job, SPAPISyncJobErrorCode.RATE_LIMITED.value, f"{exc}{retry_after}")
    except ValueError as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.DUPLICATE_DATASET.value, str(exc))
    except Exception as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.UNEXPECTED_ERROR.value, str(exc))
    session.flush()
    return sync_job


def _get_sync_job(session: Session, sync_job_id: int) -> SPAPISyncJob:
    sync_job = session.get(SPAPISyncJob, sync_job_id)
    if sync_job is None:
        raise SPAPISyncJobError("sync job not found")
    return sync_job


def _mark_failed(sync_job: SPAPISyncJob, error_code: str, error_message: str) -> None:
    sync_job.status = SPAPISyncJobStatus.FAILED.value
    sync_job.error_code = error_code
    sync_job.error_message = error_message


def _report_file_suffix(internal_report_type: str) -> str:
    output_format = get_report_type(internal_report_type).output_format
    return "tsv" if output_format == "tsv" else "json"
