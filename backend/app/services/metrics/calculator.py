from decimal import ROUND_HALF_UP, Decimal


def calculate_business_metrics(
    *,
    ordered_product_sales: Decimal,
    units_ordered: int,
    sessions: int,
) -> dict[str, Decimal]:
    return {
        "ordered_product_sales": ordered_product_sales,
        "units_ordered": Decimal(units_ordered),
        "sessions": Decimal(sessions),
        "conversion_rate": _ratio(Decimal(units_ordered), Decimal(sessions)),
    }


def calculate_ads_metrics(
    *,
    spend: Decimal,
    attributed_sales: Decimal,
    clicks: int,
    impressions: int,
    attributed_orders: int,
) -> dict[str, Decimal]:
    return {
        "spend": spend,
        "attributed_sales": attributed_sales,
        "clicks": Decimal(clicks),
        "impressions": Decimal(impressions),
        "attributed_orders": Decimal(attributed_orders),
        "acos": _ratio(spend, attributed_sales),
        "roas": _ratio(attributed_sales, spend),
        "ctr": _ratio(Decimal(clicks), Decimal(impressions)),
        "cvr": _ratio(Decimal(attributed_orders), Decimal(clicks)),
    }


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.0000")
    return (numerator / denominator).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
