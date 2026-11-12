"""Append-only Audit_Log persistence (Requirement 25, DD19)."""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence import tables as t
from acciones_ud.identity.domain.audit import AuditEntry, AuditPage, AuditQuery


def _entry(row: Any) -> AuditEntry:
    return AuditEntry(
        id=row["id"],
        actor_user_id=row["actor_user_id"],
        action=row["action"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        payload=dict(row["payload"]),
        occurred_at=row["occurred_at"],
    )


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, entry: AuditEntry) -> None:
        # No update or delete method exists; revision 0005 also rejects them in SQL.
        await self.session.execute(
            t.admin_audit_log.insert().values(
                id=entry.id,
                actor_user_id=entry.actor_user_id,
                action=entry.action,
                target_type=entry.target_type,
                target_id=entry.target_id,
                payload=entry.payload,
                occurred_at=entry.occurred_at,
            )
        )

    async def search(self, query: AuditQuery) -> AuditPage:
        table = t.admin_audit_log
        conditions: list[sa.ColumnElement[bool]] = []
        if query.action is not None:
            conditions.append(table.c.action == query.action)
        if query.actor_user_id is not None:
            conditions.append(table.c.actor_user_id == query.actor_user_id)
        if query.target_type is not None:
            conditions.append(table.c.target_type == query.target_type)
        if query.target_id is not None:
            conditions.append(table.c.target_id == query.target_id)
        filtered = sa.select(table).where(*conditions).subquery("filtered")
        page = (
            sa.select(filtered)
            .order_by(filtered.c.occurred_at.desc(), filtered.c.id.desc())
            .limit(query.limit)
            .offset(query.offset)
        ).subquery("page")
        total = (
            sa.select(sa.func.count().label("total"))
            .select_from(filtered)
            .subquery("total")
        )
        statement = (
            sa.select(total.c.total, page)
            .select_from(total)
            .outerjoin(page, sa.true())
        )
        rows = (await self.session.execute(statement)).mappings().all()
        if not rows:
            return AuditPage(items=(), total=0)
        items = [_entry(row) for row in rows if row["id"] is not None]
        return AuditPage(items=tuple(items), total=int(rows[0]["total"]))
