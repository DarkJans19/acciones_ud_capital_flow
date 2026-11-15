"""Immutable contracts shared by the MOD-04 ports (RF-10–12, RF-36–40)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

Raw = dict[str, Any]
Direction = Literal["INCOMING", "OUTGOING"]
SANDBOX_NOTICE = (
    "Virtual funds in the Alpaca sandbox environment. They do not represent real money."
)


@dataclass(frozen=True)
class LinkedAccount:
    user_id: UUID
    alpaca_account_id: str
    status: str

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"


@dataclass(frozen=True)
class BalanceView:
    status: str
    currency: str
    cash: str | None
    cash_withdrawable: str | None
    buying_power: str | None
    equity: str | None
    portfolio_value: str | None
    long_market_value: str | None
    retrieved_at: datetime
    unavailable: bool
    sandbox_notice: str = SANDBOX_NOTICE


@dataclass(frozen=True)
class BankRelationshipInput:
    account_owner_name: str
    bank_account_type: str
    bank_account_number: str
    bank_routing_number: str


@dataclass(frozen=True)
class BankRelationship:
    id: UUID
    user_id: UUID
    alpaca_account_id: str
    alpaca_relationship_id: str
    owner_name: str
    account_type: str
    account_last4: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class Transfer:
    id: UUID
    user_id: UUID
    alpaca_account_id: str
    alpaca_transfer_id: str
    bank_relationship_id: UUID
    direction: Direction
    amount: Decimal
    currency: str
    status: str
    reason: str | None
    description: str | None
    alpaca_updated_at: datetime | None
    last_confirmed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class TransferState:
    status: str
    alpaca_updated_at: datetime | None


@dataclass(frozen=True)
class TransferUpdate:
    status: str
    updated_at: datetime
    reason: str | None = None


@dataclass(frozen=True)
class Activity:
    id: str
    type: str
    date: datetime
    amount: str | None = None
    currency: str = "USD"
    direction: str | None = None
    status: str | None = None
    description: str | None = None
    side: str | None = None
    symbol: str | None = None
    qty: str | None = None
    price: str | None = None


@dataclass(frozen=True)
class ActivityQuery:
    account_id: str
    after: datetime
    until: datetime
    types: tuple[str, ...] = ()
    page_size: int = 50
    page_token: str | None = None


@dataclass(frozen=True)
class ActivityPage:
    items: list[Activity]
    next_cursor: str | None


@dataclass(frozen=True)
class Plan:
    code: Literal["monthly", "annual"]
    price: Decimal
    currency: str
    interval: str
    stripe_price_id: str


@dataclass(frozen=True)
class Subscription:
    id: UUID
    user_id: UUID
    plan: Literal["monthly", "annual"]
    status: str
    stripe_checkout_session_id: str
    stripe_subscription_id: str | None = None
    stripe_customer_id: str | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    cancel_reason: str | None = None
    cancel_requested_at: datetime | None = None
    stripe_event_created_at: datetime | None = None


@dataclass(frozen=True)
class Payment:
    id: UUID
    user_id: UUID
    subscription_id: UUID
    stripe_invoice_id: str
    plan: str
    amount: Decimal
    currency: str
    period_start: datetime | None
    period_end: datetime | None
    result: Literal["paid", "failed"]
    occurred_at: datetime


@dataclass(frozen=True)
class IdempotencyEntry:
    user_id: UUID
    idempotency_key: str
    request_hash: str
    state: str
    transfer_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class StripeEvent:
    event_id: str
    type: str
    outcome: str
    received_at: datetime


@dataclass(frozen=True)
class NotificationMarker:
    source: str
    external_id: str
    user_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class ActivityCursor:
    alpaca_account_id: str
    last_activity_id: str | None
    updated_at: datetime
