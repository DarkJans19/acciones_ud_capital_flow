from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.admin.adapters.outbound.persistence.repositories import lock
from acciones_ud.admin.domain.model import Raw

SCHEDULE_ACTIONS = (
    "market_default_schedule_set",
    "market_default_schedule_cleared",
    "schedule_override_created",
    "schedule_override_updated",
    "schedule_override_deleted",
)


class DispatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock(self, ident: UUID) -> None:
        await lock(self.session, "admin_dispatch:" + str(ident))

    async def get(self, ident: UUID) -> Raw | None:
        row = (
            (
                await self.session.execute(
                    sa.text("SELECT * FROM admin_schedule_dispatches WHERE audit_entry_id = :id"),
                    {"id": ident},
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    async def source(self, ident: UUID) -> Raw | None:
        row = (
            (
                await self.session.execute(
                    sa.text(
                        "SELECT * FROM admin_audit_log WHERE id = :id AND action IN :actions"
                    ).bindparams(sa.bindparam("actions", expanding=True)),
                    {"id": ident, "actions": SCHEDULE_ACTIONS},
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    async def insert(self, record: Raw) -> None:
        await self.session.execute(
            sa.text("""INSERT INTO admin_schedule_dispatches
            (audit_entry_id,market_code,dispatched_at,affected_orders,notified_users)
            VALUES (:audit_entry_id,:market_code,:dispatched_at,
                    :affected_orders,:notified_users)"""),
            record,
        )

    async def undispatched(self) -> list[UUID]:
        result = await self.session.execute(
            sa.text("""SELECT a.id FROM admin_audit_log a
            LEFT JOIN admin_schedule_dispatches d ON d.audit_entry_id = a.id
            WHERE a.action IN :actions AND d.audit_entry_id IS NULL
            ORDER BY a.occurred_at,a.id LIMIT 50""").bindparams(
                sa.bindparam("actions", expanding=True)
            ),
            {"actions": SCHEDULE_ACTIONS},
        )
        return list(result.scalars())

    async def history(self, market: str, start: datetime, end: datetime) -> list[Raw]:
        result = await self.session.execute(
            sa.text("""SELECT a.*,d.dispatched_at,
            d.affected_orders,d.notified_users FROM admin_audit_log a
            LEFT JOIN admin_schedule_dispatches d ON d.audit_entry_id = a.id
            WHERE a.target_type = 'market' AND a.target_id = :market AND a.action IN :actions
              AND a.occurred_at >= :start AND a.occurred_at < :end""").bindparams(
                sa.bindparam("actions", expanding=True)
            ),
            {"market": market, "start": start, "end": end, "actions": SCHEDULE_ACTIONS},
        )
        return [dict(row) for row in result.mappings()]
