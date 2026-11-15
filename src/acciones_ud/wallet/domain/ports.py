from contextlib import AbstractAsyncContextManager
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from acciones_ud.wallet.domain.model import (
    ActivityCursor,
    ActivityPage,
    ActivityQuery,
    BankRelationship,
    BankRelationshipInput,
    Direction,
    IdempotencyEntry,
    LinkedAccount,
    NotificationMarker,
    Payment,
    Raw,
    StripeEvent,
    Subscription,
    Transfer,
)


class Repository[T](Protocol):
    async def get(self, **filters: object) -> T | None: ...
    async def list(self, **filters: object) -> list[T]: ...
    async def insert(self, value: T) -> bool: ...
    async def save(self, value: T, **expected: object) -> bool: ...
    async def delete(self, **filters: object) -> None: ...


class LinkedAccountReader(Protocol):
    async def get(self, user_id: UUID) -> LinkedAccount | None: ...
    async def list_active(self) -> list[LinkedAccount]: ...


class AccountStatusWriter(Protocol):
    async def update_status(self, user_id: UUID, status: str, at: datetime) -> None: ...


class PremiumFlagWriter(Protocol):
    async def set_premium(self, user_id: UUID, value: bool) -> None: ...


class AlpacaFundingPort(Protocol):
    async def get_trading_account(self, account_id: str, timeout_s: float) -> Raw: ...
    async def create_ach_relationship(
        self,
        account_id: str,
        data: BankRelationshipInput,
    ) -> Raw: ...
    async def list_ach_relationships(self, account_id: str) -> list[Raw]: ...
    async def create_transfer(
        self,
        account_id: str,
        relationship_id: str,
        amount: Decimal,
        direction: Direction,
    ) -> Raw: ...
    async def list_transfers(self, account_id: str) -> list[Raw]: ...
    async def list_activities(self, query: ActivityQuery) -> ActivityPage: ...


class StripePort(Protocol):
    async def create_checkout_session(self, user_id: UUID, price_id: str) -> Raw: ...
    async def cancel_at_period_end(self, stripe_subscription_id: str) -> Raw: ...
    async def get_subscription(self, stripe_subscription_id: str) -> Raw: ...


class BalanceNotifierPort(Protocol):
    async def notify(self, user_id: UUID, payload: dict[str, object]) -> None: ...


class WalletWork(Protocol):
    banks: Repository[BankRelationship]
    transfers: Repository[Transfer]
    keys: Repository[IdempotencyEntry]
    subscriptions: Repository[Subscription]
    payments: Repository[Payment]
    events: Repository[StripeEvent]
    markers: Repository[NotificationMarker]
    cursors: Repository[ActivityCursor]
    accounts: LinkedAccountReader
    premium: PremiumFlagWriter

    async def lock_user(self, user_id: UUID) -> None: ...


class WalletWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[WalletWork]: ...
