from collections.abc import Mapping
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, localcontext


def quantize(value: Decimal, scale: str) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = max(40, len(value.as_tuple().digits) + abs(value.adjusted()) + 12)
        return value.quantize(Decimal(scale), rounding=ROUND_HALF_EVEN)


def money(value: Decimal) -> Decimal:
    return quantize(value, "0.01")


def qty(value: Decimal) -> Decimal:
    return quantize(value, "0.000000001")


def price(value: Decimal) -> Decimal:
    return quantize(value, "0.0001")


def pct(value: Decimal) -> Decimal:
    return quantize(value, "0.01")


def shares(parts: Mapping[str, Decimal]) -> dict[str, Decimal]:
    with localcontext() as ctx:
        ctx.prec = 40
        total = sum(parts.values(), Decimal(0))
        if total == 0:
            return {}
        raw = {key: value / total * 100 for key, value in parts.items()}
        result = {
            key: value.quantize(Decimal("0.01"), rounding=ROUND_FLOOR) for key, value in raw.items()
        }
        remaining = int((100 - sum(result.values())) * 100)
        order = sorted(parts, key=lambda key: (-(raw[key] - result[key]), key))
        for key in order[:remaining]:
            result[key] += Decimal("0.01")
        return result
