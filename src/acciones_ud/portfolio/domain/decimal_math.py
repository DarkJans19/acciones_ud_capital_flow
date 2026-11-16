"""Exact accumulation around the 40-digit moving-cost division (RF-41, D1)."""

from decimal import Decimal, localcontext


def add(*values: Decimal) -> Decimal:
    if not values:
        return Decimal(0)
    low = min(int(v.as_tuple().exponent) for v in values)
    high = max(v.adjusted() for v in values)
    with localcontext() as ctx:
        ctx.prec = max(40, high - low + len(str(len(values))) + 2)
        return sum(values, Decimal(0))
