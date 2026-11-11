"""RF-25 / Property 37: price freshness annotation."""

from dataclasses import dataclass
from datetime import datetime
from math import floor

from acciones_ud.market_data.domain.entities import Freshness

SOURCE = "alpaca"


@dataclass(frozen=True)
class CandleMeta:
    currency: str | None
    source: str
    feed: str
    is_delayed: bool


def currency_for(asset_class: str) -> str | None:
    return "USD" if asset_class == "us_equity" else None


def annotate(
    asset_class: str,
    feed: str,
    as_of: datetime | None,
    now: datetime,
    threshold_seconds: int,
    served_from_cache: bool,
) -> Freshness:
    age = None if as_of is None else max(0, floor((now - as_of).total_seconds()))
    return Freshness(
        currency=currency_for(asset_class),
        source=SOURCE,
        feed=feed,
        as_of=as_of,
        data_age_seconds=age,
        is_delayed=feed == "delayed_sip",
        is_stale=served_from_cache or age is None or age > threshold_seconds,
        served_from_cache=served_from_cache,
    )


def candle_meta(asset_class: str, feed: str) -> CandleMeta:
    return CandleMeta(
        currency=currency_for(asset_class),
        source=SOURCE,
        feed=feed,
        is_delayed=feed == "delayed_sip",
    )
