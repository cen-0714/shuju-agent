from sqlalchemy.orm import Session

from app.domain.enums import ReportType
from app.models.imports import RawDataset
from app.models.normalized import (
    NormalizedAdsSearchTermDaily,
    NormalizedBusinessDaily,
    NormalizedInventoryDaily,
    NormalizedOrderDaily,
)
from app.services.normalization.ads import normalize_ads_search_term_row
from app.services.normalization.business import normalize_business_row
from app.services.normalization.inventory import normalize_inventory_row
from app.services.normalization.orders import normalize_order_rows


def persist_normalized_rows(
    session: Session,
    dataset: RawDataset,
    rows: list[dict[str, str]],
) -> int:
    if dataset.report_type != ReportType.BUSINESS_REPORT.value:
        if dataset.report_type == ReportType.ORDERS_REPORT.value:
            return _persist_order_rows(session, dataset, rows)
        if dataset.report_type == ReportType.INVENTORY_REPORT.value:
            return _persist_inventory_rows(session, dataset, rows)
        if dataset.report_type == ReportType.ADS_SEARCH_TERM_REPORT.value:
            return _persist_ads_search_term_rows(session, dataset, rows)
        raise ValueError("unsupported report type for normalization")

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


def _persist_order_rows(
    session: Session,
    dataset: RawDataset,
    rows: list[dict[str, str]],
) -> int:
    count = 0
    for normalized in normalize_order_rows(rows):
        session.add(
            NormalizedOrderDaily(
                raw_dataset=dataset,
                seller_account_id=dataset.seller_account_id,
                marketplace_id=dataset.marketplace_id,
                report_date=normalized.report_date,
                sku=normalized.sku,
                asin=normalized.asin,
                product_name=normalized.product_name,
                currency=normalized.currency,
                units_ordered=normalized.units_ordered,
                ordered_product_sales=normalized.ordered_product_sales,
                order_count=normalized.order_count,
            )
        )
        count += 1
    return count


def _persist_inventory_rows(
    session: Session,
    dataset: RawDataset,
    rows: list[dict[str, str]],
) -> int:
    count = 0
    for row in rows:
        normalized = normalize_inventory_row(row)
        session.add(
            NormalizedInventoryDaily(
                raw_dataset=dataset,
                seller_account_id=dataset.seller_account_id,
                marketplace_id=dataset.marketplace_id,
                report_date=dataset.date_range_end,
                sku=normalized.sku,
                asin=normalized.asin,
                fulfillment_channel=normalized.fulfillment_channel,
                available_quantity=normalized.available_quantity,
                listing_status=normalized.listing_status,
                price=normalized.price,
                is_active_listing=normalized.is_active_listing,
            )
        )
        count += 1
    return count


def _persist_ads_search_term_rows(
    session: Session,
    dataset: RawDataset,
    rows: list[dict[str, str]],
) -> int:
    count = 0
    for row in rows:
        normalized = normalize_ads_search_term_row(row)
        session.add(
            NormalizedAdsSearchTermDaily(
                raw_dataset=dataset,
                seller_account_id=dataset.seller_account_id,
                marketplace_id=dataset.marketplace_id,
                report_date=normalized.report_date,
                campaign_name=normalized.campaign_name,
                search_term=normalized.search_term,
                impressions=normalized.impressions,
                clicks=normalized.clicks,
                spend=normalized.spend,
                attributed_sales=normalized.attributed_sales,
                attributed_orders=normalized.attributed_orders,
            )
        )
        count += 1
    return count
