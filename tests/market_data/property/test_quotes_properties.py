# Feature: identity-market-backend, Property 19: Snapshot mapping

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.quotes import from_snapshot

INSTANTS = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1), timezones=st.just(UTC)
)
PRICES = st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=6).map(str)
SIZES = st.integers(min_value=0, max_value=1_000_000)


def optional(strategy: st.SearchStrategy[object]) -> st.SearchStrategy[object]:
    return st.one_of(st.none(), strategy)


TRADE = st.fixed_dictionaries(
    {"p": optional(PRICES), "t": optional(INSTANTS.map(lambda value: value.isoformat()))}
)
QUOTE = st.fixed_dictionaries(
    {
        "bp": optional(PRICES),
        "bs": optional(SIZES),
        "ap": optional(PRICES),
        "as": optional(SIZES),
        "t": optional(INSTANTS.map(lambda value: value.isoformat())),
    }
)
BAR = st.fixed_dictionaries({"v": optional(SIZES)})
DOCUMENT = st.fixed_dictionaries(
    {
        "latestTrade": st.one_of(st.none(), TRADE),
        "latestQuote": st.one_of(st.none(), QUOTE),
        "dailyBar": st.one_of(st.none(), BAR),
    }
)


@given(DOCUMENT, st.sampled_from(["iex", "sip", "delayed_sip"]))
def test_snapshot_mapping_keeps_present_fields_and_nulls_omitted(
    document: dict[str, object], feed: str
) -> None:
    snapshot = from_snapshot(document, feed)

    trade = document["latestTrade"] if isinstance(document["latestTrade"], dict) else {}
    quote = document["latestQuote"] if isinstance(document["latestQuote"], dict) else {}
    bar = document["dailyBar"] if isinstance(document["dailyBar"], dict) else {}

    expected_price = None if trade.get("p") is None else Decimal(str(trade["p"]))
    expected_bid = None if quote.get("bp") is None else Decimal(str(quote["bp"]))
    expected_ask = None if quote.get("ap") is None else Decimal(str(quote["ap"]))
    expected_bid_size = quote.get("bs")
    expected_ask_size = quote.get("as")
    expected_volume = bar.get("v")

    assert snapshot.last_trade_price == expected_price
    assert snapshot.bid_price == expected_bid
    assert snapshot.ask_price == expected_ask
    assert snapshot.bid_size == expected_bid_size
    assert snapshot.ask_size == expected_ask_size
    assert snapshot.daily_volume == expected_volume
    assert snapshot.feed == feed

    instants = [
        datetime.fromisoformat(str(value))
        for value in (quote.get("t"), trade.get("t"))
        if value is not None
    ]
    expected = max(instants).astimezone(UTC) if instants else None
    assert snapshot.quote_updated_at == expected
    if snapshot.quote_updated_at is not None:
        assert snapshot.quote_updated_at.tzinfo is UTC
