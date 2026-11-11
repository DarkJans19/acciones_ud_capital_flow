# Feature: identity-market-backend, Property 20: Bars mapping

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.bars import map_bars
from acciones_ud.market_data.domain.entities import Bar

INSTANTS = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1), timezones=st.just(UTC)
)
DECIMALS = st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=6)
BARS = st.builds(
    Bar,
    timestamp=INSTANTS,
    open=DECIMALS,
    high=DECIMALS,
    low=DECIMALS,
    close=DECIMALS,
    volume=st.integers(min_value=0, max_value=1_000_000),
)


@given(
    bars=st.lists(BARS, max_size=20),
    first=INSTANTS,
    second=INSTANTS,
    page_size=st.integers(min_value=1, max_value=10000),
)
def test_bars_mapping_filters_orders_and_caps(
    bars: list[Bar], first: datetime, second: datetime, page_size: int
) -> None:
    start, end = (first, second) if first <= second else (second, first)
    page = map_bars(bars, start, end, page_size, next_page_token=None)

    expected = sorted(
        (bar for bar in bars if start <= bar.timestamp <= end),
        key=lambda bar: bar.timestamp,
    )[:page_size]
    assert page.bars == expected
    assert len(page.bars) <= page_size
    assert [bar.timestamp for bar in page.bars] == sorted(bar.timestamp for bar in page.bars)
    for bar in page.bars:
        assert start <= bar.timestamp <= end
