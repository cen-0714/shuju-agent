from app.schemas.reports import DailyReportDocument


def render_daily_report_markdown(report: DailyReportDocument) -> str:
    lines = [
        f"# Daily Amazon Report - {report.report_date.isoformat()}",
        "",
        "## Executive Summary",
        f"- Ordered product sales: {report.totals.get('ordered_product_sales', 0)}",
        f"- Units ordered: {report.totals.get('units_ordered', 0)}",
        f"- Ad spend: {report.totals.get('ad_spend', 0)}",
        f"- Ad sales: {report.totals.get('ad_sales', 0)}",
        "",
        "## Store Summary",
    ]
    for store in report.store_summaries:
        lines.append(
            f"- {store.seller_name}: sales {store.ordered_product_sales}, "
            f"units {store.units_ordered}, ACOS {store.acos}"
        )
    lines.extend(["", "## Data Freshness"])
    if report.warnings:
        lines.extend([f"- {warning}" for warning in report.warnings])
    else:
        lines.append("- No freshness warnings.")
    return "\n".join(lines) + "\n"
