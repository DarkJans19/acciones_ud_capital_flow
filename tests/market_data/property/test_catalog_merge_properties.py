# Feature: identity-market-backend, Property 18: Catalog merge preserves sectors

from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.catalog_merge import merge_asset, merge_catalog
from acciones_ud.market_data.domain.entities import Instrument

SYMBOLS = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789./-",
    min_size=1,
    max_size=6,
)
EXCHANGES = st.sampled_from(["NYSE", "NASDAQ", "AMEX", "ARCA", "OTC"])
SECTORS = st.one_of(st.none(), st.sampled_from(["Technology", "Energy", "Health Care"]))


def instrument(symbol: str, sector: str | None, exchange: str, tradable: bool) -> Instrument:
    return Instrument(
        symbol=symbol,
        name=f"{symbol} Incorporated",
        exchange=exchange,
        tradable=tradable,
        marginable=tradable,
        shortable=tradable,
        easy_to_borrow=tradable,
        fractionable=tradable,
        sector=sector,
        listed=True,
    )


def unique(items: list[tuple[str, str | None, str, bool]]) -> list[Instrument]:
    seen: dict[str, Instrument] = {}
    for symbol, sector, exchange, tradable in items:
        seen.setdefault(symbol, instrument(symbol, sector, exchange, tradable))
    return list(seen.values())


@given(
    cached=st.lists(
        st.tuples(SYMBOLS, SECTORS, EXCHANGES, st.booleans()), max_size=8
    ).map(unique),
    fetched=st.lists(
        st.tuples(SYMBOLS, st.none(), EXCHANGES, st.booleans()), max_size=8
    ).map(unique),
)
def test_catalog_merge_preserves_sectors(
    cached: list[Instrument], fetched: list[Instrument]
) -> None:
    merged = merge_catalog(cached, fetched)
    cached_by_symbol = {item.symbol: item for item in cached}
    fetched_by_symbol = {item.symbol: item for item in fetched}
    merged_by_symbol = {item.symbol: item for item in merged}

    assert set(merged_by_symbol) == set(cached_by_symbol) | set(fetched_by_symbol)
    for symbol, merged_item in merged_by_symbol.items():
        assert merged_item.listed is (symbol in fetched_by_symbol)
        if symbol in fetched_by_symbol:
            asset = fetched_by_symbol[symbol]
            assert merged_item.name == asset.name
            assert merged_item.exchange == asset.exchange
            assert merged_item.tradable == asset.tradable
            expected_sector = (
                cached_by_symbol[symbol].sector if symbol in cached_by_symbol else None
            )
            assert merged_item.sector == expected_sector
        else:
            assert replace(merged_item, listed=True) == cached_by_symbol[symbol]
        if symbol not in fetched_by_symbol:
            assert merged_item.sector == cached_by_symbol[symbol].sector


@given(
    cached=st.lists(
        st.tuples(SYMBOLS, SECTORS, EXCHANGES, st.booleans()), max_size=8
    ).map(unique),
    fetched=st.lists(
        st.tuples(SYMBOLS, st.none(), EXCHANGES, st.booleans()), min_size=1, max_size=1
    ).map(unique),
)
def test_single_asset_merge_matches_catalog_merge(
    cached: list[Instrument], fetched: list[Instrument]
) -> None:
    asset = fetched[0]
    merged = merge_asset(cached, asset)
    expected = merge_catalog(cached, [asset])
    assert merged == expected
    for item in merged:
        if item.symbol != asset.symbol:
            original = next(entry for entry in cached if entry.symbol == item.symbol)
            assert replace(item, listed=True) == original
