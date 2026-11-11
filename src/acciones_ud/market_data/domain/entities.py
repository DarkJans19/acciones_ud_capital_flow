"""Value objects of the market data domain. No infrastructure imports."""

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class InstrumentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Classification(StrEnum):
    TRADABLE = "tradable"
    VIEW_ONLY = "view_only"


class DayKind(StrEnum):
    TRADING_DAY = "trading_day"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIGGERED = "triggered"


class Comparator(StrEnum):
    ABOVE = "above"
    BELOW = "below"
    CROSSES = "crosses"


EVENT_TYPES = (
    "market_open",
    "market_close",
    "proposals",
    "approval_requests",
    "price_changes",
    "execution_confirmations",
    "daily_summary",
)
CHANNELS = ("in_app", "email", "sms", "telegram")


@dataclass(frozen=True)
class Market:
    code: str
    name: str
    timezone: str = "America/New_York"
    default_open_time: time | None = None
    default_close_time: time | None = None


@dataclass(frozen=True)
class ScheduleOverride:
    id: UUID
    market_code: str
    date: date
    closed: bool
    open_time: time | None = None
    close_time: time | None = None


@dataclass(frozen=True)
class CalendarSession:
    """One Alpaca trading day, with New York local times."""

    date: date
    open_at: time
    close_at: time


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    exchange: str
    asset_class: str = "us_equity"
    status: str = InstrumentStatus.ACTIVE
    tradable: bool = False
    marginable: bool = False
    shortable: bool = False
    easy_to_borrow: bool = False
    fractionable: bool = False
    sector: str | None = None
    listed: bool = True
    alpaca_asset_id: UUID | None = None

    @property
    def classification(self) -> Classification:
        return Classification.TRADABLE if self.tradable else Classification.VIEW_ONLY


@dataclass(frozen=True)
class Snapshot:
    last_trade_price: Decimal | None = None
    bid_price: Decimal | None = None
    ask_price: Decimal | None = None
    bid_size: int | None = None
    ask_size: int | None = None
    daily_volume: int | None = None
    quote_updated_at: datetime | None = None
    feed: str = "iex"


@dataclass(frozen=True)
class StoredSnapshot:
    snapshot: Snapshot
    retrieved_at: datetime


@dataclass(frozen=True)
class Freshness:
    currency: str | None
    source: str
    feed: str
    as_of: datetime | None
    data_age_seconds: int | None
    is_delayed: bool
    is_stale: bool
    served_from_cache: bool


@dataclass(frozen=True)
class QuoteFields:
    bid_price: Decimal | None = None
    bid_size: int | None = None
    ask_price: Decimal | None = None
    ask_size: int | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class LatestQuoteDoc:
    quote: QuoteFields | None = None


@dataclass(frozen=True)
class DepthLevel:
    bid_price: Decimal | None = None
    bid_size: int | None = None
    ask_price: Decimal | None = None
    ask_size: int | None = None


@dataclass(frozen=True)
class DepthResult:
    levels: tuple[DepthLevel, ...] = ()
    as_of: datetime | None = None
    full_depth_available: bool = False


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class BarsPage:
    bars: list[Bar] = field(default_factory=list)
    next_page_token: str | None = None


@dataclass(frozen=True)
class CalendarDay:
    date: date
    kind: DayKind
    open_at: datetime | None = None
    close_at: datetime | None = None
    override: bool = False


@dataclass(frozen=True)
class MarketClock:
    is_open: bool
    next_open: datetime
    next_close: datetime
    timestamp: datetime


@dataclass(frozen=True)
class Watchlist:
    id: UUID
    name: str
    symbols: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PriceAlert:
    id: UUID
    symbol: str
    comparator: Comparator
    threshold: Decimal
    status: AlertStatus
    created_at: datetime | None = None
    triggered_at: datetime | None = None
    user_id: UUID | None = None
    last_evaluated_price: Decimal | None = None


@dataclass(frozen=True)
class Notification:
    id: UUID
    event_type: str
    payload: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class Recipient:
    user_id: UUID
    channels: frozenset[str]
    email: str | None = None
    telegram_chat_id: str | None = None


@dataclass(frozen=True)
class PriceUpdate:
    symbol: str
    price: Decimal | None
    timestamp: datetime | None = None
