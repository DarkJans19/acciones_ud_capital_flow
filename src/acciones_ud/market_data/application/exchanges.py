"""RF-24 12.3: exchange list used by the market explorer."""

from acciones_ud.market_data.application.catalog import CatalogService
from acciones_ud.market_data.domain.entities import Market
from acciones_ud.market_data.domain.ports import CatalogWorkFactory


class ExchangesService:
    def __init__(self, uow: CatalogWorkFactory, catalog: CatalogService) -> None:
        self.uow = uow
        self.catalog = catalog

    async def list_markets(self) -> list[Market]:
        await self.catalog.ensure_fresh()
        async with self.uow() as work:
            return await work.instruments.exchanges()
