from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

Raw = dict[str, Any]


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    BROKER_SIGNED = "BROKER_SIGNED"
    EXECUTING = "EXECUTING"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    IN_REVIEW = "IN_REVIEW"
    FAILED = "FAILED"
    HELD = "HELD"


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    qty: Decimal
    type: str | None = None
    order_class: str = "simple"
    time_in_force: str = "day"
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    trail_price: Decimal | None = None
    trail_percent: Decimal | None = None
    take_profit_limit_price: Decimal | None = None
    stop_loss_stop_price: Decimal | None = None
    schedule_if_closed: bool = False
    confirmed: bool = False
    high_amount_acknowledged: bool = False


@dataclass(frozen=True)
class Order:
    id: UUID
    user_id: UUID
    alpaca_account_id: str
    symbol: str
    exchange: str
    side: str
    qty: Decimal
    type: str
    order_class: str
    time_in_force: str
    reference_price: Decimal
    estimated_amount: Decimal
    status: OrderStatus
    client_order_id: str
    created_at: datetime
    updated_at: datetime
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    trail_price: Decimal | None = None
    trail_percent: Decimal | None = None
    take_profit_limit_price: Decimal | None = None
    stop_loss_stop_price: Decimal | None = None
    status_cause: str | None = None
    provider_status: str | None = None
    alpaca_order_id: str | None = None
    filled_qty: Decimal = Decimal(0)
    filled_avg_price: Decimal | None = None
    fully_filled: bool = False
    scheduled_for: datetime | None = None
    scheduled_session_end: datetime | None = None
    returned_for_changes: bool = False
    submit_attempted_at: datetime | None = None
    lookup_misses: int = 0
    completed_at: datetime | None = None
    broker_id: UUID | None = None
    broker_signed_at: datetime | None = None
    schedule_if_closed: bool = False
    fee_version_id: UUID | None = None
    commission_rate_pct: Decimal | None = None
    platform_share_pct: Decimal | None = None


@dataclass(frozen=True)
class OrderLeg:
    order_id: UUID
    role: str
    alpaca_order_id: str | None
    price: Decimal
    provider_status: str | None = None


@dataclass(frozen=True)
class OrderEvent:
    id: UUID
    order_id: UUID
    from_status: str | None
    to_status: str
    cause: str
    actor_type: str
    actor_id: UUID | None
    at: datetime
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Execution:
    alpaca_execution_id: str
    order_id: UUID
    qty: Decimal
    price: Decimal
    executed_at: datetime
    recorded_at: datetime


@dataclass(frozen=True)
class Reservation:
    order_id: UUID
    user_id: UUID
    kind: Literal["usd", "shares"]
    symbol: str
    amount: Decimal
    status: Literal["active", "transferred", "released"]
    updated_at: datetime


@dataclass(frozen=True)
class ReauthorizationRequest:
    id: UUID
    order_id: UUID
    previous_price: Decimal
    updated_price: Decimal
    deadline: datetime
    decision: str | None = None
    answered_at: datetime | None = None
    resume_status: str = "PENDING"


@dataclass(frozen=True)
class CancelRequest:
    id: UUID
    order_id: UUID
    previous_status: str
    reason: str
    reason_text: str | None
    confirmed: bool
    requested_at: datetime
    outcome: str


@dataclass(frozen=True)
class ReviewComment:
    id: UUID
    order_id: UUID
    broker_id: UUID
    comment: str
    at: datetime


@dataclass(frozen=True)
class OrderControls:
    default_order_type: str = "market"
    daily_order_limit: int = 50
    high_order_threshold_usd: Decimal = Decimal("10000.00")
    extra_confirmation: bool = True


@dataclass(frozen=True)
class TradableAsset:
    symbol: str
    exchange: str
    active: bool
    tradable: bool
    fractionable: bool


@dataclass(frozen=True)
class LinkedAccount:
    user_id: UUID
    alpaca_account_id: str
    status: str


@dataclass(frozen=True)
class FieldError:
    field: str


@dataclass(frozen=True)
class SessionWindow:
    opens_at: datetime
    closes_at: datetime


@dataclass(frozen=True)
class IdempotencyEntry:
    user_id: UUID
    idempotency_key: str
    request_hash: str
    order_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class ScheduleChangeRecord:
    change_id: UUID
    market_code: str
    applied_at: datetime
    affected_count: int


@dataclass(frozen=True)
class ActivityCursor:
    alpaca_account_id: str
    last_activity_id: str | None
    updated_at: datetime


@dataclass(frozen=True)
class OrderConfig:
    commission_rate: Decimal = Decimal("0.02")
    reauth_deviation_pct: Decimal = Decimal("1.00")
    reauth_window_minutes: int = 30
    local_max_age_days: int = 5
    submit_timeout_seconds: float = 4
