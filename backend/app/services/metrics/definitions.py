from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinitionSeed:
    metric_name: str
    formula: str
    source_fields: tuple[str, ...]
    time_grain: str
    currency_rule: str
    version: str


def metric_definitions() -> list[MetricDefinitionSeed]:
    return [
        MetricDefinitionSeed(
            "ordered_product_sales",
            "sum sales",
            ("ordered_product_sales",),
            "day",
            "source_currency",
            "v1",
        ),
        MetricDefinitionSeed("units_ordered", "sum units", ("units_ordered",), "day", "none", "v1"),
        MetricDefinitionSeed(
            "conversion_rate",
            "units_ordered / sessions",
            ("units_ordered", "sessions"),
            "day",
            "none",
            "v1",
        ),
        MetricDefinitionSeed("spend", "sum spend", ("spend",), "day", "source_currency", "v1"),
        MetricDefinitionSeed(
            "acos",
            "spend / attributed_sales",
            ("spend", "attributed_sales"),
            "day",
            "none",
            "v1",
        ),
        MetricDefinitionSeed(
            "roas",
            "attributed_sales / spend",
            ("attributed_sales", "spend"),
            "day",
            "none",
            "v1",
        ),
        MetricDefinitionSeed(
            "ctr",
            "clicks / impressions",
            ("clicks", "impressions"),
            "day",
            "none",
            "v1",
        ),
        MetricDefinitionSeed(
            "cvr",
            "attributed_orders / clicks",
            ("attributed_orders", "clicks"),
            "day",
            "none",
            "v1",
        ),
    ]
