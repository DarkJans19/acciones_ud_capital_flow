from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

ReportType = Literal["on_demand", "daily_summary", "monthly", "broker"]
OwnerRole = Literal["investor", "broker"]
PageCursor = str


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    next_cursor: str | None = None


@dataclass(frozen=True)
class Period:
    from_: date
    to: date

    def bounds(self) -> tuple[datetime, datetime]:
        zone = ZoneInfo("America/New_York")
        return (
            datetime.combine(self.from_, time.min, zone).astimezone(UTC),
            datetime.combine(self.to + timedelta(days=1), time.min, zone).astimezone(UTC),
        )


@dataclass(frozen=True)
class LinkedAccount:
    user_id: UUID
    alpaca_account_id: str
    status: str


@dataclass(frozen=True)
class RawPosition:
    symbol: str
    exchange: str
    qty: Decimal
    qty_available: Decimal
    avg_entry_price: Decimal
    current_price: Decimal


@dataclass(frozen=True)
class ExecutionRecord:
    # Alpaca execution identifiers are text in the orders ledger, not local UUIDs.
    execution_id: str
    order_id: UUID
    user_id: UUID
    symbol: str
    exchange: str
    side: Literal["buy", "sell"]
    qty: Decimal
    price: Decimal
    executed_at: datetime
    signed_by_broker_id: UUID | None = None


@dataclass(frozen=True)
class RealizedEvent:
    execution_id: str
    executed_at: datetime
    qty: Decimal
    gross: Decimal
    net: Decimal
    cost_removed: Decimal


@dataclass(frozen=True)
class SymbolLedger:
    symbol: str
    qty: Decimal = Decimal(0)
    total_cost: Decimal = Decimal(0)
    realized_gross: Decimal = Decimal(0)
    realized_net: Decimal = Decimal(0)
    sold_cost: Decimal = Decimal(0)
    mismatch: bool = False
    events: list[RealizedEvent] = field(default_factory=list)


@dataclass(frozen=True)
class PositionValue:
    symbol: str
    exchange: str
    sector: str | None
    qty: Decimal
    reserved_qty: Decimal
    price: Decimal
    price_source: Literal["market_data", "alpaca_position"]
    average_cost: Decimal
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    reconciliation_mismatch: bool = False


@dataclass(frozen=True)
class PositionTotals:
    market_value: Decimal = Decimal(0)
    cost_basis: Decimal = Decimal(0)
    unrealized_pnl: Decimal = Decimal(0)


@dataclass(frozen=True)
class ViewSettings:
    view_type: Literal["table", "cards", "chart"] = "table"
    sort_by: Literal["symbol", "market_value", "gain_loss", "allocation"] = "symbol"
    sort_direction: Literal["asc", "desc"] = "asc"
    hide_threshold: Decimal = Decimal(0)


@dataclass(frozen=True)
class InstrumentInfo:
    symbol: str
    market: str
    sector: str | None


@dataclass(frozen=True)
class Share:
    key: str
    volume: Decimal
    percentage: Decimal


@dataclass(frozen=True)
class Statistics:
    execution_count: int
    buy_count: int
    sell_count: int
    volume: Decimal
    by_market: list[Share]
    by_instrument: list[Share]
    by_sector: list[Share]


@dataclass(frozen=True)
class RiskInputs:
    window_days: int
    execution_count: int
    traded_volume: Decimal
    market_values: list[Decimal]
    equity: Decimal | None


@dataclass(frozen=True)
class RiskProfile:
    window_days: int
    f: Decimal
    c: Decimal
    e: Decimal
    t: Decimal
    risk_score: Decimal | None
    classification: Literal["conservative", "moderate", "aggressive", "insufficient_data"]
    equity_unavailable: bool
    metrics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CommissionQuote:
    amount: Decimal
    source: Literal["reference", "official"]


@dataclass(frozen=True)
class Report:
    id: UUID
    owner_id: UUID
    owner_role: OwnerRole
    type: ReportType
    period: Period
    positions_as_of: datetime
    content: dict[str, object]
    generated_at: datetime
    notified_at: datetime | None = None
