from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.storage import LocalStorageBackend
from app.core.time import utc_now
from app.domain.enums import ImportJobStatus
from app.models.imports import ImportJob, RawReportRow
from app.models.normalized import (
    NormalizedAdsSearchTermDaily,
    NormalizedBusinessDaily,
    NormalizedInventoryDaily,
)
from app.services.reports.repository import mark_reports_stale_for_dataset


def delete_import_job(
    session: Session,
    storage: LocalStorageBackend,
    import_job_id: int,
) -> ImportJob:
    import_job = session.get(ImportJob, import_job_id)
    if import_job is None:
        raise ValueError("import job not found")
    dataset = import_job.raw_dataset
    if dataset is None:
        import_job.status = ImportJobStatus.DELETED.value
        import_job.deleted_at = utc_now()
        return import_job

    storage.delete_file(dataset.raw_file_path)
    session.execute(delete(RawReportRow).where(RawReportRow.raw_dataset_id == dataset.id))
    for model in (
        NormalizedBusinessDaily,
        NormalizedInventoryDaily,
        NormalizedAdsSearchTermDaily,
    ):
        session.execute(delete(model).where(model.raw_dataset_id == dataset.id))

    mark_reports_stale_for_dataset(session, dataset)
    import_job.status = ImportJobStatus.DELETED.value
    import_job.deleted_at = utc_now()
    session.flush()
    return import_job
