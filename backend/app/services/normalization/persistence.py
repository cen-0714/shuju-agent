from sqlalchemy.orm import Session

from app.domain.enums import ReportType
from app.models.imports import RawDataset
from app.models.normalized import NormalizedBusinessDaily
from app.services.normalization.business import normalize_business_row


def persist_normalized_rows(
    session: Session,
    dataset: RawDataset,
    rows: list[dict[str, str]],
) -> int:
    if dataset.report_type != ReportType.BUSINESS_REPORT.value:
        return 0

    count = 0
    for row in rows:
        normalized = normalize_business_row(row)
        session.add(
            NormalizedBusinessDaily(
                raw_dataset=dataset,
                seller_account_id=dataset.seller_account_id,
                marketplace_id=dataset.marketplace_id,
                report_date=normalized.report_date,
                asin=normalized.asin,
                sku=normalized.sku,
                ordered_product_sales=normalized.ordered_product_sales,
                units_ordered=normalized.units_ordered,
                sessions=normalized.sessions,
                page_views=normalized.page_views,
                conversion_rate=normalized.conversion_rate,
                buy_box_percentage=normalized.buy_box_percentage,
            )
        )
        count += 1
    return count
