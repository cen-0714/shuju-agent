from datetime import date
from decimal import Decimal

from app.services.metrics.calculator import calculate_ads_metrics, calculate_business_metrics
from app.services.metrics.definitions import metric_definitions
from app.services.metrics.freshness import freshness_for_report_date


def test_metric_definitions_include_core_metrics() -> None:
    names = {definition.metric_name for definition in metric_definitions()}

    assert "ordered_product_sales" in names
    assert "acos" in names
    assert "roas" in names


def test_calculate_business_metrics() -> None:
    metrics = calculate_business_metrics(
        ordered_product_sales=Decimal("240.00"),
        units_ordered=12,
        sessions=100,
    )

    assert metrics["ordered_product_sales"] == Decimal("240.00")
    assert metrics["conversion_rate"] == Decimal("0.1200")


def test_calculate_ads_metrics() -> None:
    metrics = calculate_ads_metrics(
        spend=Decimal("32.50"),
        attributed_sales=Decimal("120.00"),
        clicks=40,
        impressions=1000,
        attributed_orders=4,
    )

    assert metrics["acos"] == Decimal("0.2708")
    assert metrics["roas"] == Decimal("3.6923")
    assert metrics["ctr"] == Decimal("0.0400")


def test_freshness_for_report_date() -> None:
    assert (
        freshness_for_report_date(date(2026, 5, 26), today=date(2026, 5, 26)).value
        == "preliminary"
    )
    assert (
        freshness_for_report_date(date(2026, 5, 25), today=date(2026, 5, 26)).value
        == "stable"
    )
    assert (
        freshness_for_report_date(date(2026, 5, 20), today=date(2026, 5, 26)).value
        == "final"
    )
