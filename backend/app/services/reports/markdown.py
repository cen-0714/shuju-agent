from app.schemas.reports import DailyReportDocument


def render_daily_report_markdown(report: DailyReportDocument) -> str:
    lines = [
        f"# Daily Amazon Report - {report.report_date.isoformat()}",
        "",
        "## Executive Summary",
    ]
    if report.totals_by_currency:
        lines.append("- Ordered product sales by currency:")
        for total in report.totals_by_currency:
            lines.append(f"  - {total.currency}: {total.ordered_product_sales}")
    else:
        lines.append(f"- Ordered product sales: {report.totals.get('ordered_product_sales', 0)}")
    lines.extend(
        [
            f"- Units ordered: {report.totals.get('units_ordered', 0)}",
            f"- Ad spend: {report.totals.get('ad_spend', 0)}",
            f"- Ad sales: {report.totals.get('ad_sales', 0)}",
            "",
            "## Store Summary",
        ]
    )
    for store in report.store_summaries:
        currency = f" [{store.currency}]" if store.currency else ""
        lines.append(
            f"- {store.seller_name}{currency}: sales {store.ordered_product_sales}, "
            f"units {store.units_ordered}, ACOS {store.acos}"
        )
    if report.trend:
        lines.extend(["", "## 销售趋势 (Sales Trend)"])
        for point in report.trend:
            lines.append(
                f"- {point.period_label} [{point.currency}]: "
                f"sales {point.ordered_product_sales}, units {point.units_ordered}, "
                f"orders {point.order_count}"
            )
    if report.sku_performance:
        lines.extend(["", "## SKU 表现 (SKU Performance)"])
        for item in report.sku_performance:
            name = item.product_name or item.sku
            lines.append(
                f"- {item.sku} ({name}) [{item.currency}]: "
                f"sales {item.ordered_product_sales}, units {item.units_ordered}"
            )
    analysis = report.llm_analysis or {}
    if isinstance(analysis, dict) and analysis.get("summary"):
        lines.extend(["", "## AI Insights", f"- {analysis['summary']}"])
        for finding in analysis.get("findings", []):
            lines.append(f"- {finding.get('severity', 'info')}: {finding.get('title', '')}")
    lines.extend(["", "## Data Freshness"])
    if report.warnings:
        lines.extend([f"- {warning}" for warning in report.warnings])
    else:
        lines.append("- No freshness warnings.")
    return "\n".join(lines) + "\n"
