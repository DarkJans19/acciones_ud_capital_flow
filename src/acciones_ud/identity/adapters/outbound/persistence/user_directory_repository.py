"""Administrative user directory read model (Requirements 20 and 21)."""

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence import tables as t
from acciones_ud.identity.domain.directory import (
    DirectoryEntry,
    DirectoryPage,
    DirectoryQuery,
    kyc_fields,
    like_pattern,
)

Record = dict[str, Any]


def _filters(query: DirectoryQuery, now: datetime) -> list[sa.ColumnElement[bool]]:
    kyc = t.kyc_accounts
    conditions: list[sa.ColumnElement[bool]] = []
    if query.account_status is not None:
        conditions.append(t.users.c.account_status == query.account_status)
    if query.role is not None:
        conditions.append(
            sa.exists(
                sa.select(sa.literal(1)).where(
                    t.role_assignments.c.user_id == t.users.c.id,
                    t.role_assignments.c.role_code == query.role,
                    t.effective_assignment(t.role_assignments, t.users, now),
                )
            )
        )
    if query.q is not None:
        pattern = like_pattern(query.q)
        conditions.append(
            sa.or_(
                t.users.c.email.ilike(pattern, escape="\\"),
                t.users.c.first_names.ilike(pattern, escape="\\"),
                t.users.c.last_names.ilike(pattern, escape="\\"),
            )
        )
    if query.broker_requested is not None:
        conditions.append(t.users.c.broker_requested == query.broker_requested)
    if query.kyc_status is not None:
        conditions.append(
            sa.and_(kyc.c.alpaca_account_id.is_not(None), kyc.c.status == query.kyc_status)
        )
    if query.kyc_link_state == "none":
        conditions.append(kyc.c.user_id.is_(None))
    elif query.kyc_link_state == "unlinked":
        conditions.append(
            sa.and_(kyc.c.user_id.is_not(None), kyc.c.alpaca_account_id.is_(None))
        )
    elif query.kyc_link_state == "linked":
        conditions.append(kyc.c.alpaca_account_id.is_not(None))
    return conditions


def _entry(row: Any) -> DirectoryEntry:
    kyc: Record | None = None
    if row["kyc_user_id"] is not None:
        kyc = {
            "alpaca_account_id": row["kyc_alpaca_account_id"],
            "status": row["kyc_status"],
            "status_updated_at": row["kyc_status_updated_at"],
            "status_checked_at": row["kyc_status_checked_at"],
            "reserved_at": row["kyc_reserved_at"],
            "created_at": row["kyc_created_at"],
        }
    return DirectoryEntry(
        user_id=row["user_id"],
        email=row["email"],
        first_names=row["first_names"],
        last_names=row["last_names"],
        phone=row["phone"],
        country=row["country"],
        account_status=row["account_status"],
        is_premium=bool(row["is_premium"]),
        roles=tuple(sorted(row["roles"] or ())),
        broker_requested=bool(row["broker_requested"]),
        registered_at=row["registered_at"],
        **kyc_fields(kyc),
    )


class UserDirectoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _filtered(self, query: DirectoryQuery, now: datetime) -> sa.Subquery:
        roles = (
            sa.select(
                sa.func.array_agg(
                    t.role_assignments.c.role_code.distinct(), type_=ARRAY(sa.Text())
                )
            )
            .where(
                t.role_assignments.c.user_id == t.users.c.id,
                t.effective_assignment(t.role_assignments, t.users, now),
            )
            .scalar_subquery()
        )
        kyc = t.kyc_accounts
        return (
            sa.select(
                t.users.c.id.label("user_id"),
                t.users.c.email,
                t.users.c.first_names,
                t.users.c.last_names,
                t.users.c.phone,
                t.users.c.country,
                t.users.c.account_status,
                t.users.c.is_premium,
                t.users.c.broker_requested,
                t.users.c.created_at.label("registered_at"),
                roles.label("roles"),
                kyc.c.user_id.label("kyc_user_id"),
                kyc.c.alpaca_account_id.label("kyc_alpaca_account_id"),
                kyc.c.status.label("kyc_status"),
                kyc.c.status_updated_at.label("kyc_status_updated_at"),
                kyc.c.status_checked_at.label("kyc_status_checked_at"),
                kyc.c.reserved_at.label("kyc_reserved_at"),
                kyc.c.created_at.label("kyc_created_at"),
            )
            .select_from(t.users.outerjoin(kyc, kyc.c.user_id == t.users.c.id))
            .where(*_filters(query, now))
            .subquery("filtered")
        )

    async def _page(
        self, query: DirectoryQuery, now: datetime, *, user_id: UUID | None = None
    ) -> tuple[list[DirectoryEntry], int]:
        filtered = self._filtered(query, now)
        page = (
            sa.select(filtered)
            .order_by(filtered.c.registered_at.desc(), filtered.c.user_id.asc())
            .limit(query.limit)
            .offset(query.offset)
        )
        total = sa.select(sa.func.count().label("total")).select_from(filtered)
        if user_id is not None:
            page = page.where(filtered.c.user_id == user_id)
            total = total.where(filtered.c.user_id == user_id)
        page_subquery = page.subquery("page")
        total_subquery = total.subquery("total")
        statement = (
            sa.select(total_subquery.c.total, page_subquery)
            .select_from(total_subquery)
            .outerjoin(page_subquery, sa.true())
        )
        rows = (await self.session.execute(statement)).mappings().all()
        if not rows:
            return [], 0
        total_value = int(rows[0]["total"])
        items = [_entry(row) for row in rows if row["user_id"] is not None]
        return items, total_value

    async def search(self, query: DirectoryQuery, now: datetime) -> DirectoryPage:
        items, total = await self._page(query, now)
        return DirectoryPage(items=tuple(items), total=total)

    async def get(self, user_id: UUID, now: datetime) -> DirectoryEntry | None:
        query = DirectoryQuery(limit=1, offset=0)
        items, _ = await self._page(query, now, user_id=user_id)
        return items[0] if items else None
