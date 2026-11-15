from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, WithJsonSchema

from acciones_ud.wallet.domain.model import SANDBOX_NOTICE

Money = Annotated[
    Decimal,
    PlainSerializer(str, return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^-?[0-9]+(?:\.[0-9]+)?$"}),
]
DecimalString = Annotated[str, Field(pattern=r"^[0-9]+(?:\.[0-9]+)?$", max_length=40)]


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BalanceOut(Output):
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


class CurrenciesOut(Output):
    currencies: list[str]
    conversion_supported: Literal[False] = False


class BankIn(BaseModel):
    account_owner_name: str = Field(min_length=1, max_length=200)
    bank_account_type: Literal["CHECKING", "SAVINGS"]
    bank_account_number: str = Field(pattern=r"^[0-9]{4,17}$", repr=False)
    bank_routing_number: str = Field(pattern=r"^[0-9]{9}$", repr=False)


class BankOut(Output):
    id: UUID
    alpaca_relationship_id: str
    owner_name: str
    account_type: str
    account_last4: str
    status: str
    created_at: datetime


class TransferIn(BaseModel):
    bank_relationship_id: UUID
    amount: DecimalString
    currency: str = "USD"


class TransferOut(Output):
    id: UUID
    alpaca_transfer_id: str
    bank_relationship_id: UUID
    direction: Literal["INCOMING", "OUTGOING"]
    amount: Money
    currency: str
    status: str
    reason: str | None
    description: str | None
    alpaca_updated_at: datetime | None
    last_confirmed_at: datetime | None
    created_at: datetime
    sandbox_notice: str = SANDBOX_NOTICE


class ActivityOut(Output):
    id: str
    type: str
    date: datetime
    amount: str | None
    currency: str
    direction: str | None
    status: str | None
    description: str | None
    side: str | None
    symbol: str | None
    qty: str | None
    price: str | None


class PageOut[T](Output):
    items: list[T]
    next_cursor: str | None


class PlanOut(Output):
    code: Literal["monthly", "annual"]
    price: Money
    currency: str
    interval: str


class CheckoutIn(BaseModel):
    plan: Literal["monthly", "annual"]


class CheckoutOut(Output):
    checkout_session_id: str
    url: str


class CancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class SubscriptionOut(Output):
    id: UUID
    plan: Literal["monthly", "annual"]
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    cancel_reason: str | None
    cancel_requested_at: datetime | None


class PaymentOut(Output):
    id: UUID
    stripe_invoice_id: str
    plan: str
    amount: Money
    currency: str
    period_start: datetime | None
    period_end: datetime | None
    result: Literal["paid", "failed"]
    occurred_at: datetime


class CurrentSubscriptionOut(Output):
    subscription: SubscriptionOut | None
    plan: PlanOut | None
    latest_payment: PaymentOut | None
    next_charge_at: datetime | None


class ReceivedOut(Output):
    received: bool
