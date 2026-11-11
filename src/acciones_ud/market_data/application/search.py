"""RF-24: instrument search with pagination and filters."""

from acciones_ud.market_data.application.catalog import CatalogService
from acciones_ud.market_data.domain.entities import Instrument
from acciones_ud.market_data.domain.ports import CatalogWorkFactory
from acciones_ud.market_data.domain.search import PAGE_SIZE, normalize_query


class SearchService:
    def __init__(self, uow: CatalogWorkFactory, catalog: CatalogService) -> None:
        self.uow = uow
        self.catalog = catalog

    async def search(
        self,
        query: str,
        exchange: str | None,
        classification: str | None,
        page: int,
    ) -> tuple[list[Instrument], int, int]:
        normalized = normalize_query(query)
        await self.catalog.ensure_fresh()
        async with self.uow() as work:
            results, total = await work.instruments.search(
                normalized, exchange, classification, page, PAGE_SIZE
            )
        return results, total, PAGE_SIZE
