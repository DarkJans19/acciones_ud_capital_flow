from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence import tables as t
from acciones_ud.identity.adapters.outbound.persistence.interest_catalog_repository import (
    InterestCatalogRepository,
)
from acciones_ud.identity.adapters.outbound.persistence.rbac_repository import missing
from acciones_ud.identity.domain.auth_ports import Record


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def user(self, user_id: UUID, *, lock: bool = False) -> Record:
        query = sa.select(t.users).where(t.users.c.id == user_id)
        if lock:
            query = query.with_for_update()
        row = (await self.session.execute(query)).mappings().first()
        if not row:
            raise missing("user")
        return dict(row)

    async def preferences(self, user_id: UUID) -> list[dict[str, object]]:
        rows = (
            (
                await self.session.execute(
                    sa.select(t.notification_preferences).where(
                        t.notification_preferences.c.user_id == user_id
                    )
                )
            )
            .mappings()
            .all()
        )
        return [
            {"event_type": r["event_type"], "channel": r["channel"], "enabled": r["enabled"]}
            for r in rows
        ]

    async def save_preferences(self, user_id: UUID, values: list[dict[str, object]]) -> None:
        for entry in values:
            await self.session.execute(
                t.notification_preferences.update()
                .where(
                    t.notification_preferences.c.user_id == user_id,
                    t.notification_preferences.c.event_type == entry["event_type"],
                    t.notification_preferences.c.channel == entry["channel"],
                )
                .values(enabled=entry["enabled"])
            )

    def settings_table(self, kind: str) -> sa.Table:
        return t.portfolio_view_settings if kind == "portfolio" else t.order_controls

    async def settings(self, user_id: UUID, kind: str) -> Record | None:
        table = self.settings_table(kind)
        row = (
            (await self.session.execute(sa.select(table).where(table.c.user_id == user_id)))
            .mappings()
            .first()
        )
        return {k: v for k, v in row.items() if k not in ("user_id", "updated_at")} if row else None

    async def save_settings(self, user_id: UUID, kind: str, values: Record) -> None:
        table = self.settings_table(kind)
        await self.session.execute(
            insert(table)
            .values(user_id=user_id, **values)
            .on_conflict_do_update(
                index_elements=[table.c.user_id], set_={**values, "updated_at": sa.func.now()}
            )
        )

    async def update_user(self, user_id: UUID, values: Record) -> None:
        await self.session.execute(
            t.users.update()
            .where(t.users.c.id == user_id)
            .values(**values, updated_at=sa.func.now())
        )

    async def known_interests(self) -> list[str]:
        return await InterestCatalogRepository(self.session).known_interests()
