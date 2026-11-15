from decimal import ROUND_UP, Decimal, localcontext
from typing import Literal

from acciones_ud.orders.domain.model import OrderControls


def base_price(
    order_type: str,
    limit_price: Decimal | None,
    stop_price: Decimal | None,
    reference_price: Decimal,
) -> Decimal:
    if order_type in {"limit", "stop_limit"}:
        if limit_price is None:
            raise ValueError("limit_price required")
        return limit_price
    if order_type == "stop":
        if stop_price is None:
            raise ValueError("stop_price required")
        return stop_price
    return reference_price


def estimated_amount(
    side: str, qty: Decimal, base_price: Decimal, commission_rate: Decimal
) -> Decimal:
    with localcontext() as context:
        context.prec = max(
            context.prec,
            len(qty.as_tuple().digits)
            + len(base_price.as_tuple().digits)
            + len(commission_rate.as_tuple().digits)
            + 8,
            qty.adjusted() + base_price.adjusted() + 12,
        )
        multiplier = 1 + commission_rate if side == "buy" else Decimal(1)
        return (qty * base_price * multiplier).quantize(Decimal("0.01"), rounding=ROUND_UP)


def requires_extra_authorization(
    amount: Decimal, controls: OrderControls
) -> Literal["none", "totp", "acknowledgement"]:
    if amount <= controls.high_order_threshold_usd:
        return "none"
    return "totp" if controls.extra_confirmation else "acknowledgement"
