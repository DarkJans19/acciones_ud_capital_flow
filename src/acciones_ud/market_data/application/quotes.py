"""RF-25: live quote with a stored-snapshot fallback (Property 38)."""

from dataclasses import dataclass

from acciones_ud.market_data.domain.entities import Freshness, Snapshot
from acciones_ud.market_data.domain.freshness import annotate
from acciones_ud.market_data.domain.ports import (
    AlpacaDataPort,
    QuoteWorkFactory,
)
from acciones_ud.market_data.domain.quotes import choose_quote
from acciones_ud.market_data.domain.symbols import validate_symbol
from acciones_ud.shared.domain.alpaca_errors import AlpacaError
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


@dataclass(frozen=True)
class QuoteView:
    symbol: str
    snapshot: Snapshot
    freshness: Freshness


class QuoteService:
    def __init__(
        self,
        uow: QuoteWorkFactory,
        data: AlpacaDataPort,
        clock: Clock,
        threshold_seconds: int,
    ) -> None:
        self.uow = uow
        self.data = data
        self.clock = clock
        self.threshold_seconds = threshold_seconds

    async def quote(self, raw_symbol: str) -> QuoteView:
        symbol = validate_symbol(raw_symbol)
        async with self.uow() as work:
            instrument = await work.instruments.get(symbol)
            if instrument is None:
                raise AppError(404, ErrorCode.SYMBOL_NOT_FOUND, "Symbol not found.")
            stored = await work.snapshots.get(symbol)

        live: Snapshot | None = None
        failure: AlpacaError | None = None
        try:
            live = await self.data.snapshot(symbol)
        except AlpacaError as exc:
            failure = exc

        snapshot, served_from_cache = choose_quote(live, stored, failure)
        now = self.clock.now()
        if not served_from_cache:
            async with self.uow() as work:
                await work.snapshots.save(symbol, snapshot, now)

        freshness = annotate(
            instrument.asset_class,
            snapshot.feed,
            snapshot.quote_updated_at,
            now,
            self.threshold_seconds,
            served_from_cache,
        )
        return QuoteView(symbol=symbol, snapshot=snapshot, freshness=freshness)
