from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.admin.adapters.outbound.persistence import tables as t
from acciones_ud.admin.domain import model as m
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.reports import canonical_value
from acciones_ud.shared.domain.audit_entry import AuditRecord


async def lock(session: AsyncSession, key: str) -> None:
    await session.execute(
        sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": key}
    )


class _Rows[T]:
    def __init__(self, session: AsyncSession, table: sa.Table, entity: type[T]) -> None:
        self.session, self.table, self.entity = session, table, entity

    async def _list(self, *conditions: sa.ColumnElement[bool], locked: bool = False) -> list[T]:
        query = sa.select(self.table).where(*conditions)
        if locked:
            query = query.with_for_update()
        return [self.entity(**row) for row in (await self.session.execute(query)).mappings()]

    async def _insert(self, values: dict[str, Any]) -> None:
        await self.session.execute(sa.insert(self.table).values(**values))

    async def _get(self, ident: UUID, locked: bool = False) -> T | None:
        rows = await self._list(self.table.c.id == ident, locked=locked)
        return rows[0] if rows else None


class FeeRepository(_Rows[m.FeeVersion]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.fees, m.FeeVersion)

    async def lock_scope(self, scope: str) -> None:
        await lock(self.session, "admin_fee:" + scope)

    async def all_versions(self) -> list[m.FeeVersion]:
        return await self._list()

    async def insert(self, value: m.FeeVersion) -> None:
        await self._insert(asdict(value))

    async def get_for_update(self, ident: UUID) -> m.FeeVersion | None:
        return await self._get(ident, True)

    async def cancel(self, ident: UUID, at: datetime, actor: UUID, reason: str) -> bool:
        result = await self.session.execute(
            sa.update(t.fees)
            .where(
                t.fees.c.id == ident,
                t.fees.c.canceled_at.is_(None),
                t.fees.c.effective_from > at,
            )
            .values(canceled_at=at, canceled_by=actor, cancel_reason=reason)
            .returning(t.fees.c.id)
        )
        return result.first() is not None


class HaltRepository(_Rows[m.TradingHalt]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.halts, m.TradingHalt)

    async def lock_scope(self, scope: str) -> None:
        await lock(self.session, "admin_halt:" + scope)

    async def all(self) -> list[m.TradingHalt]:
        return await self._list()

    async def insert(self, value: m.TradingHalt) -> None:
        await self._insert(asdict(value))

    async def get_for_update(self, ident: UUID) -> m.TradingHalt | None:
        return await self._get(ident, True)

    async def release(self, ident: UUID, at: datetime, actor: UUID, reason: str) -> bool:
        result = await self.session.execute(
            sa.update(t.halts)
            .where(
                t.halts.c.id == ident,
                t.halts.c.released_at.is_(None),
            )
            .values(released_at=at, released_by=actor, release_reason=reason)
            .returning(t.halts.c.id)
        )
        return result.first() is not None


class RestrictionRepository(_Rows[m.AccountRestriction]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.restrictions, m.AccountRestriction)

    async def lock_user(self, user: UUID) -> None:
        await lock(self.session, "admin_restriction:" + str(user))

    async def all(self, user_id: UUID | None = None) -> list[m.AccountRestriction]:
        return await self._list(*([t.restrictions.c.user_id == user_id] if user_id else []))

    async def insert(self, value: m.AccountRestriction) -> None:
        await self._insert(asdict(value))

    async def get_for_update(self, ident: UUID) -> m.AccountRestriction | None:
        return await self._get(ident, True)

    async def lift(self, value: m.AccountRestriction) -> bool:
        values = {k: v for k, v in asdict(value).items() if k.startswith("lift")}
        result = await self.session.execute(
            sa.update(t.restrictions)
            .where(
                t.restrictions.c.id == value.id,
                t.restrictions.c.lifted_at.is_(None),
            )
            .values(**values)
            .returning(t.restrictions.c.id)
        )
        return result.first() is not None


class AuditWriter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, record: AuditRecord) -> None:
        from acciones_ud.identity.adapters.outbound.persistence.tables import admin_audit_log

        values = asdict(record)
        values["payload"] = canonical_value(record.payload)
        await self._session.execute(sa.insert(admin_audit_log).values(**values))


class ReportRepository(_Rows[m.ComplianceReport]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.reports, m.ComplianceReport)

    async def insert(self, value: m.ComplianceReport) -> None:
        values = asdict(value)
        values["content"] = canonical_value(value.content)
        await self._insert(values)

    async def get(self, ident: UUID) -> m.ComplianceReport | None:
        return await self._get(ident)

    async def for_user(self, user: UUID) -> list[m.ComplianceReport]:
        return await self._list(t.reports.c.user_id == user)


class SnapshotRepository(_Rows[m.KpiSnapshot]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.snapshots, m.KpiSnapshot)

    async def get(self, period: Period, version: str) -> m.KpiSnapshot | None:
        rows = await self._list(
            t.snapshots.c.period_from == period.from_,
            t.snapshots.c.period_to == period.to,
            t.snapshots.c.definitions_version == version,
        )
        return rows[0] if rows else None

    async def upsert(self, value: m.KpiSnapshot) -> None:
        values = asdict(value)
        values["payload"] = canonical_value(value.payload)
        statement = insert(t.snapshots).values(**values)
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=["period_from", "period_to", "definitions_version"],
                set_={
                    "payload": statement.excluded.payload,
                    "computed_at": statement.excluded.computed_at,
                },
            )
        )
