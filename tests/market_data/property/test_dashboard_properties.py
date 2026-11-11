# Feature: identity-market-backend, Property 16: Dashboard assembly

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.dashboard import MAX_INSTRUMENTS, assemble
from acciones_ud.market_data.domain.entities import Instrument, Snapshot

SYMBOLS = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=5)
EXCHANGES = st.sampled_from(["NYSE", "NASDAQ", "AMEX"])
SECTORS = st.one_of(st.none(), st.sampled_from(["Technology", "Energy", "Health Care"]))

INSTRUMENTS = st.lists(
    st.tuples(SYMBOLS, EXCHANGES, SECTORS, st.booleans()), max_size=15
).map(
    lambda items: [
        Instrument(
            symbol=symbol,
            name=f"{symbol} Inc.",
            exchange=exchange,
            sector=sector,
            listed=listed,
        )
        for symbol, exchange, sector, listed in {
            item[0]: item for item in items
        }.values()
    ]
)

INTERESTS = st.lists(
    st.one_of(
        st.sampled_from(["NYSE", "NASDAQ", "AMEX", "Technology", "Energy"]),
        st.text(min_size=1, max_size=8),
    ),
    max_size=5,
)
DEFAULTS = st.lists(SYMBOLS, max_size=6)

QUOTES = st.dictionaries(
    SYMBOLS,
    st.builds(
        Snapshot,
        last_trade_price=st.one_of(
            st.none(),
            st.decimals(min_value=Decimal("0"), max_value=Decimal("1000"), places=2),
        ),
        quote_updated_at=st.one_of(
            st.none(),
            st.just(datetime(2026, 1, 2, 12, tzinfo=UTC)),
        ),
    ),
    max_size=10,
)


def reference(
    instruments: list[Instrument], interests: list[str], defaults: list[str]
) -> tuple[list[str], str]:
    wanted = {interest.lower() for interest in interests}
    matching = [
        item
        for item in instruments
        if item.listed
        and (
            item.exchange.lower() in wanted
            or (item.sector is not None and item.sector.lower() in wanted)
        )
    ]
    if matching:
        return sorted(item.symbol for item in matching)[:MAX_INSTRUMENTS], "interests"
    by_symbol = {item.symbol: item for item in instruments}
    fallback = [
        by_symbol[symbol] for symbol in defaults if symbol in by_symbol and by_symbol[symbol].listed
    ]
    return sorted(item.symbol for item in fallback)[:MAX_INSTRUMENTS], "default"


@given(
    INSTRUMENTS,
    INTERESTS,
    DEFAULTS,
    QUOTES,
    st.one_of(st.none(), st.sampled_from(["beginner", "experienced"])),
)
def test_dashboard_assembly(
    instruments: list[Instrument],
    interests: list[str],
    defaults: list[str],
    quotes: dict[str, Snapshot],
    level: str | None,
) -> None:
    data = assemble(instruments, interests, defaults, quotes, level)
    expected, source = reference(instruments, interests, defaults)

    assert [item.symbol for item in data.instruments] == expected
    assert len(data.instruments) <= MAX_INSTRUMENTS
    assert data.source == source
    assert data.level == level
    assert data.beginner is (level == "beginner")

    for item in data.instruments:
        quote = quotes.get(item.symbol)
        if quote is None or quote.last_trade_price is None:
            assert item.quote_unavailable is True
            assert item.price is None
            assert item.quote_timestamp is None
        else:
            assert item.quote_unavailable is False
            assert item.price == quote.last_trade_price
            assert item.quote_timestamp == quote.quote_updated_at
