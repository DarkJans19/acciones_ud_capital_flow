import base64
import builtins
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.orders.adapters.outbound.persistence.tables import events, executions, orders
from acciones_ud.orders.adapters.outbound.persistence.tables import reservations as r
from acciones_ud.orders.application.execution_ledger import LedgerExecution, LedgerFilters
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def query(
    user_id: UUID | None, until: datetime | None, since: datetime | None, symbol: str | None
) -> sa.Select[tuple[object, ...]]:
    signer = (
        sa.select(events.c.actor_id)
        .where(
            events.c.order_id == orders.c.id,
            events.c.to_status == "BROKER_SIGNED",
            events.c.actor_type == "broker",
        )
        .order_by(events.c.at.desc(), events.c.id.desc())
        .limit(1)
        .correlate(orders)
        .lateral("signer")
    )
    statement = sa.select(
        executions.c.alpaca_execution_id.label("execution_id"),
        executions.c.order_id,
        orders.c.user_id,
        orders.c.symbol,
        orders.c.exchange,
        orders.c.side,
        executions.c.qty,
        executions.c.price,
        executions.c.executed_at,
        signer.c.actor_id.label("signed_by_broker_id"),
        orders.c.fee_version_id,
        orders.c.commission_rate_pct,
        orders.c.platform_share_pct,
    ).select_from(
        executions.join(orders, executions.c.order_id == orders.c.id).outerjoin(signer, sa.true())
    )
    if user_id is not None:
        statement = statement.where(orders.c.user_id == user_id)
    if until is not None:
        statement = statement.where(executions.c.executed_at < until)
    if since is not None:
        statement = statement.where(executions.c.executed_at >= since)
    if symbol is not None:
        statement = statement.where(orders.c.symbol == symbol)
    return statement.order_by(
        executions.c.executed_at.desc(), executions.c.alpaca_execution_id.desc()
    )


class ExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_platform_page(
        self,
        since: datetime,
        until: datetime,
        cursor: str | None,
        size: int,
        filters: LedgerFilters | None = None,
    ) -> tuple[builtins.list[LedgerExecution], str | None]:
        filters = filters or LedgerFilters()
        return await self._page(
            filters.user_id, since, until, filters.symbol, cursor, size, 1000, filters
        )

    async def volume(self, since: datetime, until: datetime) -> builtins.list[dict[str, object]]:
        result = await self.session.execute(
            sa.select(
                orders.c.exchange,
                orders.c.side,
                sa.func.sum(executions.c.qty * executions.c.price).label("gross_amount"),
                sa.func.count().label("executions_count"),
            )
            .select_from(executions.join(orders, orders.c.id == executions.c.order_id))
            .where(
                executions.c.executed_at >= since,
                executions.c.executed_at < until,
            )
            .group_by(orders.c.exchange, orders.c.side)
        )
        return [dict(row) for row in result.mappings()]

    async def list(
        self,
        user_id: UUID,
        until: datetime | None = None,
        since: datetime | None = None,
        symbol: str | None = None,
    ) -> builtins.list[LedgerExecution]:
        rows = (await self.session.execute(query(user_id, until, since, symbol))).mappings()
        return [LedgerExecution(**row) for row in rows]

    async def list_page(
        self,
        user_id: UUID,
        since: datetime,
        until: datetime,
        symbol: str | None,
        cursor: str | None,
        size: int,
    ) -> tuple[builtins.list[LedgerExecution], str | None]:
        return await self._page(user_id, since, until, symbol, cursor, size, 100)

    async def _page(
        self,
        user_id: UUID | None,
        since: datetime,
        until: datetime,
        symbol: str | None,
        cursor: str | None,
        size: int,
        maximum: int,
        filters: LedgerFilters | None = None,
    ) -> tuple[builtins.list[LedgerExecution], str | None]:
        if not 1 <= size <= maximum:
            raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: page_size")
        statement = query(user_id, until, since, symbol)
        if filters:
            if filters.broker_id is not None:
                statement = statement.where(
                    statement.selected_columns.signed_by_broker_id == filters.broker_id
                )
            if filters.market is not None:
                statement = statement.where(orders.c.exchange == filters.market)
            if filters.investor_ids is not None:
                statement = statement.where(orders.c.user_id.in_(filters.investor_ids))
        if cursor:
            try:
                raw = base64.b64decode(cursor.encode(), altchars=b"-_", validate=True).decode()
                at, ident = raw.split("|", 1)
                instant = datetime.fromisoformat(at)
                if instant.tzinfo is None or not ident or len(ident) > 256:
                    raise ValueError()
            except (ValueError, UnicodeError):
                raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: cursor") from None
            statement = statement.where(
                sa.tuple_(executions.c.executed_at, executions.c.alpaca_execution_id)
                < (instant, ident)
            )
        rows = (await self.session.execute(statement.limit(size + 1))).mappings()
        values = [LedgerExecution(**row) for row in rows]
        selected = values[:size]
        next_cursor = None
        if len(values) > size:
            last = selected[-1]
            next_cursor = base64.urlsafe_b64encode(
                f"{last.executed_at.isoformat()}|{last.execution_id}".encode()
            ).decode()
        return selected, next_cursor

    async def active_share_reservations(self, user_id: UUID) -> dict[str, Decimal]:
        rows = await self.session.execute(
            sa.select(r.c.symbol, sa.func.sum(r.c.amount))
            .where(r.c.user_id == user_id, r.c.kind == "shares", r.c.status == "active")
            .group_by(r.c.symbol)
        )
        return {row[0]: row[1] for row in rows}


@asynccontextmanager
async def ledger_uow() -> AsyncIterator[ExecutionRepository]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:
        yield ExecutionRepository(session)
