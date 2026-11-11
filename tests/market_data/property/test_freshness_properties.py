# Feature: identity-market-backend, Property 37: Freshness fields follow their formulas

from datetime import UTC, datetime
from math import floor

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.freshness import annotate, candle_meta

INSTANTS = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1), timezones=st.just(UTC)
)
FEEDS = st.sampled_from(["iex", "sip", "delayed_sip"])
ASSET_CLASSES = st.sampled_from(["us_equity", "us_option", "crypto"])


@given(
    asset_class=ASSET_CLASSES,
    feed=FEEDS,
    as_of=st.one_of(st.none(), INSTANTS),
    now=INSTANTS,
    threshold=st.integers(min_value=1, max_value=86400),
    served_from_cache=st.booleans(),
)
def test_freshness_fields_follow_their_formulas(
    asset_class: str,
    feed: str,
    as_of: datetime | None,
    now: datetime,
    threshold: int,
    served_from_cache: bool,
) -> None:
    freshness = annotate(asset_class, feed, as_of, now, threshold, served_from_cache)

    expected_age = (
        None if as_of is None else max(0, floor((now - as_of).total_seconds()))
    )
    expected_stale = (
        served_from_cache
        or expected_age is None
        or expected_age > threshold
    )
    assert freshness.currency == ("USD" if asset_class == "us_equity" else None)
    assert freshness.source == "alpaca"
    assert freshness.feed == feed
    assert freshness.as_of is as_of
    assert freshness.data_age_seconds == expected_age
    assert freshness.is_delayed is (feed == "delayed_sip")
    assert freshness.is_stale is expected_stale
    assert freshness.served_from_cache is served_from_cache


@given(asset_class=ASSET_CLASSES, feed=FEEDS)
def test_candle_metadata_is_the_documented_subset(asset_class: str, feed: str) -> None:
    meta = candle_meta(asset_class, feed)
    assert meta.currency == ("USD" if asset_class == "us_equity" else None)
    assert meta.source == "alpaca"
    assert meta.feed == feed
    assert meta.is_delayed is (feed == "delayed_sip")
