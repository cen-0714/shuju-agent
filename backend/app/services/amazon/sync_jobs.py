import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import AmazonAuthorizationStatus, SPAPISyncJobStatus
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
from app.models.settings import Marketplace, SellerAccount
from app.services.amazon.report_types import ReportTypeDisabledError, require_enabled_report_type


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

    normalized_options = {
        "dateGranularity": str(report_options.get("dateGranularity") or "DAY"),
        "asinGranularity": str(report_options.get("asinGranularity") or "SKU"),
    }
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
