"""RF-26: watchlist use cases with premium-independent limits and ownership."""

from uuid import UUID

from acciones_ud.market_data.domain.entities import Watchlist
from acciones_ud.market_data.domain.ports import WatchlistWorkFactory
from acciones_ud.market_data.domain.symbols import validate_symbol
from acciones_ud.market_data.domain.watchlists import (
    ensure_can_add,
    ensure_can_create,
    validate_name,
)
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def _missing() -> AppError:
    return AppError(
        404, ErrorCode.NOT_FOUND, "Watchlist not found.", {"resource": "watchlist"}
    )


class WatchlistService:
    def __init__(self, uow: WatchlistWorkFactory, clock: Clock) -> None:
        self.uow = uow
        self.clock = clock

    async def list_watchlists(self, user_id: UUID) -> list[Watchlist]:
        async with self.uow() as work:
            return await work.watchlists.list_all(user_id)

    async def get(self, user_id: UUID, watchlist_id: UUID) -> Watchlist:
        async with self.uow() as work:
            watchlist = await work.watchlists.get(user_id, watchlist_id)
            if watchlist is None:
                raise _missing()
            return watchlist

    async def create(self, user_id: UUID, raw_name: str) -> Watchlist:
        name = validate_name(raw_name)
        async with self.uow() as work:
            await work.watchlists.lock_owner(user_id)
            ensure_can_create(await work.watchlists.count(user_id))
            return await work.watchlists.create(user_id, name, self.clock.now())

    async def add_symbol(
        self, user_id: UUID, watchlist_id: UUID, raw_symbol: str
    ) -> Watchlist:
        symbol = validate_symbol(raw_symbol)
        async with self.uow() as work:
            if not await work.instruments.exists(symbol):
                raise AppError(404, ErrorCode.SYMBOL_NOT_FOUND, "Symbol not found.")
            await work.watchlists.lock_owner(user_id)
            watchlist = await work.watchlists.get(user_id, watchlist_id)
            if watchlist is None:
                raise _missing()
            ensure_can_add(watchlist.symbols, symbol)
            return await work.watchlists.add_symbol(
                user_id, watchlist_id, symbol, self.clock.now()
            )

    async def remove_symbol(
        self, user_id: UUID, watchlist_id: UUID, raw_symbol: str
    ) -> Watchlist:
        symbol = validate_symbol(raw_symbol)
        async with self.uow() as work:
            watchlist = await work.watchlists.remove_symbol(user_id, watchlist_id, symbol)
            if watchlist is None:
                raise _missing()
            return watchlist
