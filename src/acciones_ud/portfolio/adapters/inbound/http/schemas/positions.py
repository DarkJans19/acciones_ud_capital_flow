from datetime import datetime
from typing import Literal

from acciones_ud.portfolio.adapters.inbound.http.schemas.common import DecimalStr, Output


class PositionResponse(Output):
    symbol: str
    exchange: str
    sector: str | None
    qty: DecimalStr
    reserved_qty: DecimalStr
    price: DecimalStr
    price_source: Literal["market_data", "alpaca_position"]
    average_cost: DecimalStr
    market_value: DecimalStr
    cost_basis: DecimalStr
    unrealized_pnl: DecimalStr
    reconciliation_mismatch: bool


class PositionTotalsResponse(Output):
    market_value: DecimalStr
    cost_basis: DecimalStr
    unrealized_pnl: DecimalStr


class PositionsResponse(Output):
    positions: list[PositionResponse]
    totals: PositionTotalsResponse
    view_type: Literal["table", "cards", "chart"]
    positions_as_of: datetime
    currency: Literal["USD"]
