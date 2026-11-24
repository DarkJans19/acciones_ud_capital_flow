"""Read-only cross-module ledger (MOD-05 RF-41, D2/D3)."""

import builtins
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class LedgerFilters:
    user_id: UUID | None = None
    broker_id: UUID | None = None
    market: str | None = None
    symbol: str | None = None
    investor_ids: tuple[UUID, ...] | None = None


@dataclass(frozen=True)
class LedgerExecution:
    execution_id: str
    order_id: UUID
    user_id: UUID
    symbol: str
    exchange: str
    side: Literal["buy", "sell"]
    qty: Decimal
    price: Decimal
    executed_at: datetime
    signed_by_broker_id: UUID | None
    fee_version_id: UUID | None = None
    commission_rate_pct: Decimal | None = None
    platform_share_pct: Decimal | None = None


class LedgerRepository(Protocol):
    async def list_platform_page(
        self,
        since: datetime,
        until: datetime,
        cursor: str | None,
        size: int,
        filters: LedgerFilters | None = None,
    ) -> tuple[builtins.list[LedgerExecution], str | None]: ...
    async def volume(
        self, since: datetime, until: datetime
    ) -> builtins.list[dict[str, object]]: ...
    async def list(
        self,
        user_id: UUID,
        until: datetime | None = None,
        since: datetime | None = None,
        symbol: str | None = None,
    ) -> builtins.list[LedgerExecution]: ...
    async def list_page(
        self,
        user_id: UUID,
        since: datetime,
        until: datetime,
        symbol: str | None,
        cursor: str | None,
        size: int,
    ) -> tuple[builtins.list[LedgerExecution], str | None]: ...
    async def active_share_reservations(self, user_id: UUID) -> dict[str, Decimal]: ...


class LedgerFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[LedgerRepository]: ...


class ExecutionLedger:
    def __init__(self, repository: LedgerFactory) -> None:
        self.repository = repository

    async def list_platform_page(
        self,
        since: datetime,
        until: datetime,
        cursor: str | None,
        size: int = 1000,
        filters: LedgerFilters | None = None,
    ) -> tuple[builtins.list[LedgerExecution], str | None]:
        async with self.repository() as repo:
            return await repo.list_platform_page(since, until, cursor, size, filters)

    async def iterate_platform(
        self,
        since: datetime,
        until: datetime,
        batch: int = 1000,
        filters: LedgerFilters | None = None,
    ) -> AsyncIterator[LedgerExecution]:
        cursor = None
        while True:
            items, cursor = await self.list_platform_page(since, until, cursor, batch, filters)
            for item in items:
                yield item
            if cursor is None:
                break

    async def volume(self, since: datetime, until: datetime) -> builtins.list[dict[str, object]]:
        async with self.repository() as repo:
            return await repo.volume(since, until)

    async def list(
        self,
        user_id: UUID,
        until: datetime | None = None,
        since: datetime | None = None,
        symbol: str | None = None,
    ) -> builtins.list[LedgerExecution]:
        async with self.repository() as repo:
            return await repo.list(user_id, until, since, symbol)

    async def list_page(
        self,
        user_id: UUID,
        since: datetime,
        until: datetime,
        symbol: str | None,
        cursor: str | None,
        size: int,
    ) -> tuple[builtins.list[LedgerExecution], str | None]:
        async with self.repository() as repo:
            return await repo.list_page(user_id, since, until, symbol, cursor, size)

    async def active_share_reservations(self, user_id: UUID) -> dict[str, Decimal]:
        async with self.repository() as repo:
            return await repo.active_share_reservations(user_id)
