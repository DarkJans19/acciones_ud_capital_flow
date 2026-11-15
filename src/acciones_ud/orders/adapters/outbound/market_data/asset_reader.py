from collections.abc import Callable

from acciones_ud.market_data.application.catalog import CatalogService
from acciones_ud.market_data.domain.ports import CatalogWorkFactory
from acciones_ud.orders.domain.model import TradableAsset


class MarketAssetReader:
    def __init__(self, uow: CatalogWorkFactory, catalog: Callable[[], CatalogService]) -> None:
        self.uow, self.catalog = uow, catalog

    async def get(self, symbol: str) -> TradableAsset | None:
        await self.catalog().ensure_fresh()
        async with self.uow() as work:
            value = await work.instruments.get(symbol)
        if value is None:
            return None
        return TradableAsset(
            value.symbol,
            value.exchange,
            value.status == "active",
            value.tradable,
            value.fractionable,
        )
