from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from acciones_ud.portfolio.domain import model as m
from acciones_ud.portfolio.domain import rounding


@dataclass(frozen=True)
class PositionsView:
    positions: list[m.PositionValue]
    totals: m.PositionTotals
    view_type: str
    positions_as_of: datetime
    currency: str = "USD"


@dataclass(frozen=True)
class ExecutionView:
    execution_id: str
    order_id: UUID
    symbol: str
    exchange: str
    side: str
    qty: Decimal
    price: Decimal
    executed_at: datetime
    commission: Decimal
    commission_source: str


def position(value: m.PositionValue) -> m.PositionValue:
    return replace(
        value,
        qty=rounding.qty(value.qty),
        reserved_qty=rounding.qty(value.reserved_qty),
        price=rounding.price(value.price),
        average_cost=rounding.price(value.average_cost),
        market_value=rounding.money(value.market_value),
        cost_basis=rounding.money(value.cost_basis),
        unrealized_pnl=rounding.money(value.unrealized_pnl),
    )


def totals(value: m.PositionTotals) -> m.PositionTotals:
    return m.PositionTotals(
        rounding.money(value.market_value),
        rounding.money(value.cost_basis),
        rounding.money(value.unrealized_pnl),
    )


def execution(value: m.ExecutionRecord, commission: m.CommissionQuote) -> ExecutionView:
    return ExecutionView(
        value.execution_id,
        value.order_id,
        value.symbol,
        value.exchange,
        value.side,
        rounding.qty(value.qty),
        rounding.price(value.price),
        value.executed_at,
        rounding.money(commission.amount),
        commission.source,
    )


def statistics(value: m.Statistics) -> m.Statistics:
    def shares(values: list[m.Share]) -> list[m.Share]:
        return [replace(s, volume=rounding.money(s.volume)) for s in values]

    return replace(
        value,
        volume=rounding.money(value.volume),
        by_market=shares(value.by_market),
        by_instrument=shares(value.by_instrument),
        by_sector=shares(value.by_sector),
    )


def serialize(value: object) -> object:
    """Immutable JSON report content: only output DTOs enter this boundary."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return serialize(asdict(value))
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [serialize(v) for v in value]
    return value


def document(value: dict[str, object]) -> dict[str, object]:
    return {key: serialize(item) for key, item in value.items()}
