"""RF-26: watchlists and their symbols."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.market_data.domain.entities import Watchlist
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def _watchlist(row: Any, symbols: list[str]) -> Watchlist:
    mapping = cast("dict[str, Any]", row._mapping)
    return Watchlist(id=mapping["id"], name=str(mapping["name"]), symbols=symbols)


class WatchlistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self, user_id: UUID) -> list[Watchlist]:
        rows = (
            await self.session.execute(
                sa.text(
                    "SELECT id, name FROM watchlists WHERE user_id = :user "
                    "ORDER BY created_at NULLS LAST, id"
                ),
                {"user": user_id},
            )
        ).all()
        return [_watchlist(row, await self.symbols(row.id)) for row in rows]

    async def get(self, user_id: UUID, watchlist_id: UUID) -> Watchlist | None:
        row = (
            await self.session.execute(
                sa.text(
                    "SELECT id, name FROM watchlists WHERE id = :id AND user_id = :user"
                ),
                {"id": watchlist_id, "user": user_id},
            )
        ).first()
        if row is None:
            return None
        return _watchlist(row, await self.symbols(watchlist_id))

    async def lock_owner(self, user_id: UUID) -> None:
        await self.session.execute(
            sa.text("SELECT id FROM users WHERE id = :user FOR UPDATE"), {"user": user_id}
        )

    async def count(self, user_id: UUID) -> int:
        value = await self.session.scalar(
            sa.text("SELECT count(*) FROM watchlists WHERE user_id = :user"),
            {"user": user_id},
        )
        return int(value or 0)

    async def create(self, user_id: UUID, name: str, now: datetime) -> Watchlist:
        watchlist_id = uuid4()
        await self.session.execute(
            sa.text(
                "INSERT INTO watchlists (id, user_id, name, created_at) "
                "VALUES (:id, :user, :name, :now)"
            ),
            {"id": watchlist_id, "user": user_id, "name": name, "now": now},
        )
        return Watchlist(id=watchlist_id, name=name, symbols=[])

    async def add_symbol(
        self, user_id: UUID, watchlist_id: UUID, symbol: str, now: datetime
    ) -> Watchlist:
        try:
            await self.session.execute(
                sa.text(
                    "INSERT INTO watchlist_items (watchlist_id, symbol, added_at) "
                    "VALUES (:id, :symbol, :now)"
                ),
                {"id": watchlist_id, "symbol": symbol, "now": now},
            )
        except IntegrityError:
            raise AppError(
                409,
                ErrorCode.SYMBOL_ALREADY_IN_WATCHLIST,
                "The symbol is already in the watchlist.",
            ) from None
        watchlist = await self.get(user_id, watchlist_id)
        if watchlist is None:
            raise AppError(404, ErrorCode.NOT_FOUND, "Watchlist not found.")
        return watchlist

    async def remove_symbol(
        self, user_id: UUID, watchlist_id: UUID, symbol: str
    ) -> Watchlist | None:
        watchlist = await self.get(user_id, watchlist_id)
        if watchlist is None:
            return None
        await self.session.execute(
            sa.text(
                "DELETE FROM watchlist_items WHERE watchlist_id = :id AND symbol = :symbol"
            ),
            {"id": watchlist_id, "symbol": symbol},
        )
        return await self.get(user_id, watchlist_id)

    async def symbols(self, watchlist_id: UUID) -> list[str]:
        rows = await self.session.execute(
            sa.text(
                "SELECT symbol FROM watchlist_items WHERE watchlist_id = :id "
                "ORDER BY added_at NULLS LAST, symbol"
            ),
            {"id": watchlist_id},
        )
        values: list[object] = list(rows.scalars())
        return [str(value) for value in values]
