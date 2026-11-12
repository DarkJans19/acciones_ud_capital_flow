# Feature: identity-market-backend, Property 17: Search matches a reference model

import asyncio

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.application.search import SearchService
from acciones_ud.market_data.domain.entities import Instrument
from tests.support.market_fakes import MemoryInstruments, catalog_uow

SYMBOLS = st.sampled_from(
    ["AAPL", "AAP", "MSFT", "MS", "TSLA", "A", "AA", "KO", "BRK.B", "BRK/B"]
)
NAMES = st.sampled_from(
    ["Apple Inc.", "Microsoft Corporation", "Tesla", "Coca Cola", "Berkshire"]
)
EXCHANGES = st.sampled_from(["NASDAQ", "NYSE", "AMEX"])
QUERIES = st.sampled_from(["aapl", "a", "ms", "apple", "BRK.B", "brk/b", "tsla", "ko"])
CLASSIFICATIONS = st.one_of(st.none(), st.sampled_from(["tradable", "view_only"]))


class NoRefresh:
    async def ensure_fresh(self) -> None:
        return None


def make_instrument(
    symbol: str, name: str, exchange: str, tradable: bool
) -> Instrument:
    return Instrument(symbol=symbol, name=name, exchange=exchange, tradable=tradable)


def reference(
    items: list[Instrument],
    query: str,
    exchange: str | None,
    classification: str | None,
    page: int,
) -> tuple[list[str], int]:
    """Independent model: substring match, rank groups and symbol ordering."""
    needle = query.lower()
    ranked: list[tuple[int, str]] = []
    for item in items:
        symbol = item.symbol.lower()
        if symbol == needle:
            rank = 0
        elif symbol.startswith(needle):
            rank = 1
        elif needle in item.name.lower():
            rank = 2
        else:
            continue
        if exchange is not None and item.exchange != exchange:
            continue
        if classification is not None and item.classification.value != classification:
            continue
        ranked.append((rank, item.symbol))
    ranked.sort()
    start = (page - 1) * 50
    return [symbol for _, symbol in ranked[start : start + 50]], len(ranked)


@given(
    instruments=st.lists(
        st.builds(
            make_instrument,
            symbol=SYMBOLS,
            name=NAMES,
            exchange=EXCHANGES,
            tradable=st.booleans(),
        ),
        max_size=10,
    ),
    query=QUERIES,
    exchange=st.one_of(st.none(), EXCHANGES),
    classification=CLASSIFICATIONS,
    page=st.integers(min_value=1, max_value=3),
)
def test_search_matches_the_reference_model(
    instruments: list[Instrument],
    query: str,
    exchange: str | None,
    classification: str | None,
    page: int,
) -> None:
    repository = MemoryInstruments(instruments)
    service = SearchService(catalog_uow(repository), NoRefresh())  # type: ignore[arg-type]

    results, total, page_size = asyncio.run(
        service.search(query, exchange, classification, page)
    )
    expected_symbols, expected_total = reference(
        list(repository.items.values()), query, exchange, classification, page
    )

    assert [item.symbol for item in results] == expected_symbols
    assert total == expected_total
    assert page_size == 50
