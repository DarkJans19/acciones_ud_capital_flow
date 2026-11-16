from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from acciones_ud.brokers.domain.errors import QuoteUnavailableError, ValidationError


def reference_price(type: str, limit_price: Decimal | None, last_price: Decimal | None) -> Decimal:
    if type == "limit":
        if limit_price is None or not limit_price.is_finite() or limit_price <= 0:
            raise ValidationError("limit_price")
        return limit_price
    if type != "market":
        raise ValidationError("type")
    if last_price is None or not last_price.is_finite() or last_price <= 0:
        raise QuoteUnavailableError()
    return last_price


def estimated_cost(qty: Decimal, price: Decimal, rate: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 40
        return (qty * price * (1 + rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def requires_totp(cost: Decimal, threshold: Decimal) -> bool:
    return cost >= threshold
