from acciones_ud.market_data.domain.ports import CatalogWorkFactory
from acciones_ud.portfolio.domain.model import InstrumentInfo


class InstrumentReader:
    def __init__(self, catalog: CatalogWorkFactory) -> None:
        self.catalog = catalog

    async def classify(self, symbols: set[str]) -> dict[str, InstrumentInfo]:
        values: dict[str, InstrumentInfo] = {}
        async with self.catalog() as work:
            for symbol in sorted(symbols):
                instrument = await work.instruments.get(symbol)
                if instrument:
                    values[symbol] = InstrumentInfo(symbol, instrument.exchange, instrument.sector)
        return values
