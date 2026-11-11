# Feature: identity-market-backend, Property 39: Depth never fabricates levels

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.depth import from_latest_quote
from acciones_ud.market_data.domain.entities import LatestQuoteDoc, QuoteFields

PRICES = st.one_of(
    st.none(), st.decimals(min_value=Decimal("0"), max_value=Decimal("100000"), places=4)
)
SIZES = st.one_of(st.none(), st.integers(min_value=0, max_value=1_000_000))
TIMESTAMPS = st.one_of(
    st.none(),
    st.datetimes(
        min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1), timezones=st.just(UTC)
    ),
)
QUOTES = st.builds(
    QuoteFields,
    bid_price=PRICES,
    bid_size=SIZES,
    ask_price=PRICES,
    ask_size=SIZES,
    timestamp=TIMESTAMPS,
)
DOCUMENTS = st.one_of(
    st.none().map(lambda _: LatestQuoteDoc(quote=None)),
    QUOTES.map(lambda quote: LatestQuoteDoc(quote=quote)),
)


@given(DOCUMENTS)
def test_depth_never_fabricates_levels(document: LatestQuoteDoc) -> None:
    result = from_latest_quote(document)

    assert result.full_depth_available is False
    if document.quote is None:
        assert result.levels == ()
        assert result.as_of is None
        return

    assert len(result.levels) == 1
    level = result.levels[0]
    assert level.bid_price == document.quote.bid_price
    assert level.bid_size == document.quote.bid_size
    assert level.ask_price == document.quote.ask_price
    assert level.ask_size == document.quote.ask_size
    assert result.as_of == document.quote.timestamp
