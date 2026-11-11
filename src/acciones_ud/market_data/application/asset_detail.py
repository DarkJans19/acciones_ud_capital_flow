"""RF-28 / 16: asset detail read-through with a single-instrument upsert."""

from acciones_ud.market_data.domain.entities import Instrument
from acciones_ud.market_data.domain.ports import (
    AlpacaBrokerMarketPort,
    CatalogWorkFactory,
)
from acciones_ud.market_data.domain.symbols import validate_symbol
from acciones_ud.shared.domain.alpaca_errors import AlpacaError, to_app_error
from acciones_ud.shared.domain.clock import Clock


class AssetDetailService:
    def __init__(
        self,
        uow: CatalogWorkFactory,
        broker: AlpacaBrokerMarketPort,
        clock: Clock,
    ) -> None:
        self.uow = uow
        self.broker = broker
        self.clock = clock

    async def detail(self, raw_symbol: str) -> Instrument:
        symbol = validate_symbol(raw_symbol)
        try:
            asset = await self.broker.get_asset(symbol)
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        async with self.uow() as work:
            await work.instruments.upsert_one(asset, self.clock.now())
        return asset
