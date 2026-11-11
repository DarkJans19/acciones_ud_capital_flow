"""RFP-08: dashboard assembly with a 3-second budget and degraded fallbacks."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from acciones_ud.market_data.domain.dashboard import (
    DashboardData,
    assemble,
    select_instruments,
)
from acciones_ud.market_data.domain.ports import (
    AlpacaBrokerMarketPort,
    AlpacaDataPort,
    DashboardWorkFactory,
)
from acciones_ud.shared.domain.alpaca_errors import AlpacaError

QUOTE_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class DashboardView:
    market_status: str | None
    market_status_unavailable: bool
    data: DashboardData


class DashboardService:
    def __init__(
        self,
        uow: DashboardWorkFactory,
        data: AlpacaDataPort,
        broker: AlpacaBrokerMarketPort,
        default_symbols: list[str],
    ) -> None:
        self.uow = uow
        self.data = data
        self.broker = broker
        self.default_symbols = default_symbols

    async def dashboard(self, user_id: UUID) -> DashboardView:
        async with self.uow() as work:
            interests, level = await work.profile.profile(user_id)
            instruments = await work.instruments.all_listed()

        selected, _ = select_instruments(instruments, interests, self.default_symbols)
        try:
            quotes = await asyncio.wait_for(
                self.data.snapshots([item.symbol for item in selected]),
                timeout=QUOTE_TIMEOUT_SECONDS,
            )
        except (TimeoutError, AlpacaError):
            quotes = {}

        try:
            clock = await asyncio.wait_for(
                self.broker.clock(), timeout=QUOTE_TIMEOUT_SECONDS
            )
        except (TimeoutError, AlpacaError):
            market_status: str | None = None
            unavailable = True
        else:
            market_status = "open" if clock.is_open else "closed"
            unavailable = False

        return DashboardView(
            market_status=market_status,
            market_status_unavailable=unavailable,
            data=assemble(
                instruments, interests, self.default_symbols, quotes, level
            ),
        )
