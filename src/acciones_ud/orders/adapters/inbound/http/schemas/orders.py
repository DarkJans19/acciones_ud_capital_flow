from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StrictBool,
    WithJsonSchema,
)

from acciones_ud.orders.domain.model import OrderRequest, OrderStatus, Raw

Money = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value, "f"), return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^-?[0-9]+(?:\.[0-9]+)?$"}),
]
DecimalString = Annotated[str, Field(pattern=r"^[0-9]+(?:\.[0-9]+)?$", max_length=40)]
OrderType = Literal["market", "limit", "stop", "stop_limit", "trailing_stop"]
Tif = Literal["day", "gtc", "ioc", "fok"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TakeProfitIn(Input):
    limit_price: DecimalString


class StopLossIn(Input):
    stop_price: DecimalString


class OrderIn(Input):
    symbol: str = Field(min_length=1, max_length=32)
    side: Literal["buy", "sell"]
    qty: DecimalString
    type: OrderType | None = None
    order_class: Literal["simple", "bracket"] = "simple"
    time_in_force: Tif = "day"
    limit_price: DecimalString | None = None
    stop_price: DecimalString | None = None
    trail_price: DecimalString | None = None
    trail_percent: DecimalString | None = None
    take_profit: TakeProfitIn | None = None
    stop_loss: StopLossIn | None = None
    schedule_if_closed: StrictBool = False
    confirmed: StrictBool = False
    totp_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$", repr=False)
    high_amount_acknowledged: StrictBool = False

    def to_request(self) -> OrderRequest:
        return OrderRequest(
            self.symbol,
            self.side,
            Decimal(self.qty),
            self.type,
            self.order_class,
            self.time_in_force,
            Decimal(self.limit_price) if self.limit_price is not None else None,
            Decimal(self.stop_price) if self.stop_price is not None else None,
            Decimal(self.trail_price) if self.trail_price is not None else None,
            Decimal(self.trail_percent) if self.trail_percent is not None else None,
            Decimal(self.take_profit.limit_price) if self.take_profit else None,
            Decimal(self.stop_loss.stop_price) if self.stop_loss else None,
            self.schedule_if_closed,
            self.confirmed,
            self.high_amount_acknowledged,
        )


class ResubmitIn(Input):
    qty: DecimalString | None = None
    limit_price: DecimalString | None = None
    stop_price: DecimalString | None = None
    trail_price: DecimalString | None = None
    trail_percent: DecimalString | None = None
    time_in_force: Tif | None = None
    take_profit: TakeProfitIn | None = None
    stop_loss: StopLossIn | None = None
    totp_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$", repr=False)
    high_amount_acknowledged: StrictBool | None = None

    def changes(self) -> Raw:
        result: Raw = {}
        for name in self.model_fields_set - {"totp_code"}:
            value = getattr(self, name)
            if name == "take_profit":
                result["take_profit_limit_price"] = Decimal(value.limit_price) if value else None
            elif name == "stop_loss":
                result["stop_loss_stop_price"] = Decimal(value.stop_price) if value else None
            elif name in {"qty", "limit_price", "stop_price", "trail_price", "trail_percent"}:
                result[name] = Decimal(value) if value is not None else None
            else:
                result[name] = value
        return result


class CancelIn(Input):
    reason: Literal["price_changed", "no_longer_needed", "input_error", "other"]
    reason_text: str | None = Field(default=None, min_length=1, max_length=500)
    confirmed: StrictBool = False


class ReauthorizationIn(Input):
    decision: Literal["accept", "reject"]


class ReturnIn(Input):
    comment: str = Field(min_length=1, max_length=500)


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PreviewOut(Output):
    reference_price: Money
    estimated_amount: Money
    reference_commission: Money
    reference_commission_estimated: Literal[True] = True
    available_buying_power: Money
    requires_extra_authorization: bool
    authorization_method: Literal["none", "totp", "acknowledgement"]
    market_open: bool
    scheduled_for: datetime | None


class OrderSummary(Output):
    id: UUID
    status: OrderStatus
    status_cause: str | None
    provider_status: str | None
    created_at: datetime
    updated_at: datetime
    symbol: str
    exchange: str
    side: Literal["buy", "sell"]
    qty: Money
    filled_qty: Money
    filled_avg_price: Money | None
    fully_filled: bool
    type: OrderType
    order_class: Literal["simple", "bracket"]
    time_in_force: Tif
    limit_price: Money | None
    stop_price: Money | None
    trail_price: Money | None
    trail_percent: Money | None
    reference_price: Money
    estimated_amount: Money
    scheduled_for: datetime | None
    returned_for_changes: bool
    alpaca_order_id: str | None
    completed_at: datetime | None
    broker_id: UUID | None
    broker_signed_at: datetime | None


class LegOut(Output):
    role: Literal["take_profit", "stop_loss"]
    alpaca_order_id: str | None
    price: Money
    provider_status: str | None


class EventOut(Output):
    id: UUID
    from_status: OrderStatus | None
    to_status: OrderStatus
    cause: str
    actor_type: Literal["investor", "broker", "system"]
    actor_id: UUID | None
    metadata: dict[str, object]
    at: datetime


class ExecutionOut(Output):
    alpaca_execution_id: str
    qty: Money
    price: Money
    executed_at: datetime
    recorded_at: datetime


class ReservationOut(Output):
    kind: Literal["usd", "shares"]
    symbol: str
    amount: Money
    status: Literal["active", "transferred", "released"]
    updated_at: datetime


class ReauthorizationOut(Output):
    id: UUID
    previous_price: Money
    updated_price: Money
    deadline: datetime
    decision: str | None
    answered_at: datetime | None


class CancelOut(Output):
    id: UUID
    previous_status: OrderStatus
    reason: str
    reason_text: str | None
    confirmed: bool
    requested_at: datetime
    outcome: Literal["applied", "pending", "not_applied"]


class ReviewCommentOut(Output):
    id: UUID
    broker_id: UUID
    comment: str
    at: datetime


class OrderOut(OrderSummary):
    fee_version_id: UUID | None = None
    commission_rate_pct: Decimal | None = None
    platform_share_pct: Decimal | None = None
    reference_commission: Money
    reference_commission_estimated: Literal[True] = True
    legs: list[LegOut]
    executions: list[ExecutionOut]
    events: list[EventOut]
    reservation: ReservationOut | None
    reauthorizations: list[ReauthorizationOut]
    cancels: list[CancelOut]
    review_comments: list[ReviewCommentOut]


class OrderPageOut(Output):
    items: list[OrderSummary]
    next_cursor: str | None
