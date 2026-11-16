from collections.abc import Iterable
from decimal import Decimal, localcontext

from acciones_ud.portfolio.domain.model import (
    PositionTotals,
    PositionValue,
    RawPosition,
    ViewSettings,
)


def value(raw: RawPosition, quote: Decimal | None, reserved_local: Decimal) -> PositionValue:
    with localcontext() as ctx:
        ctx.prec = 40
        price = raw.current_price if quote is None else quote
        market_value = raw.qty * price
        cost = raw.qty * raw.avg_entry_price
        return PositionValue(
            raw.symbol,
            raw.exchange,
            None,
            raw.qty,
            raw.qty - raw.qty_available + reserved_local,
            price,
            "alpaca_position" if quote is None else "market_data",
            raw.avg_entry_price,
            market_value,
            cost,
            market_value - cost,
        )


def arrange(
    values: Iterable[PositionValue],
    settings: ViewSettings,
) -> tuple[list[PositionValue], PositionTotals]:
    items = sorted(values, key=lambda p: p.symbol)
    with localcontext() as ctx:
        ctx.prec = 40
        totals = PositionTotals(
            *(
                sum((getattr(p, field) for p in items), Decimal(0))
                for field in ("market_value", "cost_basis", "unrealized_pnl")
            )
        )
    if settings.sort_by == "symbol":
        items.sort(key=lambda p: p.symbol, reverse=settings.sort_direction == "desc")
    else:
        field = "unrealized_pnl" if settings.sort_by == "gain_loss" else "market_value"
        items.sort(key=lambda p: getattr(p, field), reverse=settings.sort_direction == "desc")
    return [p for p in items if p.market_value >= settings.hide_threshold], totals
