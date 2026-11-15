from decimal import Decimal


def requires_reauthorization(
    order_type: str,
    waited: bool,
    reference_price: Decimal,
    current_price: Decimal,
    threshold_pct: Decimal,
) -> bool:
    return (
        order_type == "market"
        and waited
        and (abs(current_price - reference_price) * 100 > reference_price * threshold_pct)
    )
