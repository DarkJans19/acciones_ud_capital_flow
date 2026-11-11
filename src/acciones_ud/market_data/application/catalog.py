"""RF-24/28: keep the instrument catalog fresh with a degraded cache fallback."""

from datetime import datetime, timedelta

from acciones_ud.market_data.domain.ports import (
    AlpacaBrokerMarketPort,
    CatalogWorkFactory,
)
from acciones_ud.shared.domain.alpaca_errors import AlpacaError, to_app_error
from acciones_ud.shared.domain.clock import Clock


class CatalogService:
    def __init__(
        self,
        uow: CatalogWorkFactory,
        broker: AlpacaBrokerMarketPort,
        clock: Clock,
        max_age_hours: int,
    ) -> None:
        self.uow = uow
        self.broker = broker
        self.clock = clock
        self.max_age_hours = max_age_hours

    def _fresh(self, last: datetime, now: datetime) -> bool:
        return now < last + timedelta(hours=self.max_age_hours)

    async def ensure_fresh(self) -> None:
        async with self.uow() as work:
            last = await work.instruments.catalog_last_reload()
            populated = await work.instruments.has_instruments()
        now = self.clock.now()
        if populated and last is not None and self._fresh(last, now):
            return
        try:
            assets = await self.broker.list_assets()
        except AlpacaError as exc:
            if populated:
                return
            raise to_app_error(exc) from None
        async with self.uow() as work:
            await work.instruments.upsert_catalog(assets, now)
            await work.instruments.set_catalog_last_reload(now)

    async def exists(self, symbol: str) -> bool:
        async with self.uow() as work:
            return await work.instruments.exists(symbol)
