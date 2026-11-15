from contextlib import AbstractAsyncContextManager
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from acciones_ud.orders.domain import model as m

OrderEventType = Literal["order_executions", "order_updates"]
CancelOutcome = Literal["accepted", "not_cancelable"]


class Repository[T](Protocol):
    async def get(self, **filters: object) -> T | None: ...
    async def list(self, **filters: object) -> list[T]: ...
    async def insert(self, value: T) -> bool: ...
    async def save(self, value: T, **expected: object) -> bool: ...
    async def delete(self, **filters: object) -> None: ...


class OrderRepository(Repository[m.Order], Protocol):
    async def change(self, value: m.Order, previous: m.Order, event: m.OrderEvent) -> bool: ...

    async def daily_count(self, user_id: UUID, now: datetime) -> int: ...
    async def due(self, now: datetime) -> list[m.Order]: ...

    async def page(
        self,
        user_id: UUID,
        status: str | None,
        symbol: str | None,
        start: datetime | None,
        end: datetime | None,
        page_size: int,
        cursor: str | None,
    ) -> tuple[list[m.Order], str | None]: ...


class OrderWork(Protocol):
    orders: OrderRepository
    legs: Repository[m.OrderLeg]
    events: Repository[m.OrderEvent]
    executions: Repository[m.Execution]
    reservations: Repository[m.Reservation]
    reauthorizations: Repository[m.ReauthorizationRequest]
    cancels: Repository[m.CancelRequest]
    comments: Repository[m.ReviewComment]
    keys: Repository[m.IdempotencyEntry]
    schedule_changes: Repository[m.ScheduleChangeRecord]
    cursors: Repository[m.ActivityCursor]

    async def lock_user(self, user_id: UUID) -> None: ...


class OrderWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[OrderWork]: ...


class AccountReader(Protocol):
    async def get(self, user_id: UUID) -> m.LinkedAccount | None: ...


class OrderControlsReader(Protocol):
    async def get(self, user_id: UUID) -> m.OrderControls: ...


class TotpVerifier(Protocol):
    async def has_active_totp(self, user_id: UUID) -> bool: ...
    async def verify(self, user_id: UUID, code: str, at: datetime) -> bool: ...


class QuoteReader(Protocol):
    async def current_price(self, symbol: str) -> Decimal | None: ...


class AssetReader(Protocol):
    async def get(self, symbol: str) -> m.TradableAsset | None: ...


class MarketSessionPort(Protocol):
    async def is_open(self, exchange: str, at: datetime) -> bool: ...
    async def next_open(self, exchange: str, at: datetime) -> m.SessionWindow: ...


class BuyingPowerPort(Protocol):
    async def buying_power(self, alpaca_account_id: str) -> Decimal: ...


class PositionPort(Protocol):
    async def qty_available(self, alpaca_account_id: str, symbol: str) -> Decimal: ...


class AlpacaOrdersPort(Protocol):
    async def create(self, account_id: str, submission: m.Raw, timeout_s: float) -> m.Raw: ...
    async def get_by_client_order_id(
        self, account_id: str, client_order_id: str
    ) -> m.Raw | None: ...
    async def get(self, account_id: str, alpaca_order_id: str) -> m.Raw: ...
    async def cancel(self, account_id: str, alpaca_order_id: str) -> CancelOutcome: ...
    async def list_fills(self, account_id: str, after_id: str | None) -> list[m.Raw]: ...


class BrokerLinkPort(Protocol):
    async def reviewing_broker(self, investor_id: UUID) -> UUID | None: ...
    async def is_linked(self, broker_id: UUID, investor_id: UUID) -> bool: ...
    async def linked_investors(self, broker_id: UUID) -> list[UUID]: ...


class OrderNotifierPort(Protocol):
    async def notify(
        self, user_id: UUID, event_type: OrderEventType, payload: dict[str, object]
    ) -> None: ...
