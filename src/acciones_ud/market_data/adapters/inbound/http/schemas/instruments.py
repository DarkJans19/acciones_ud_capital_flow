"""HTTP contracts for the market explorer (MOD-02)."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from acciones_ud.market_data.application.candles import CandleView
from acciones_ud.market_data.application.depth import DepthView
from acciones_ud.market_data.application.quotes import QuoteView
from acciones_ud.market_data.domain.entities import Bar, Instrument, Market


class MarketOut(BaseModel):
    code: str
    name: str

    @classmethod
    def of(cls, market: Market) -> "MarketOut":
        return cls(code=market.code, name=market.name)


class InstrumentOut(BaseModel):
    symbol: str
    name: str
    exchange: str
    asset_class: str
    status: str
    sector: str | None
    classification: str

    @classmethod
    def of(cls, instrument: Instrument) -> "InstrumentOut":
        return cls(
            symbol=instrument.symbol,
            name=instrument.name,
            exchange=instrument.exchange,
            asset_class=instrument.asset_class,
            status=instrument.status,
            sector=instrument.sector,
            classification=instrument.classification.value,
        )


class SearchOut(BaseModel):
    page: int
    page_size: int
    total: int
    results: list[InstrumentOut]


class AssetDetailOut(BaseModel):
    symbol: str
    name: str
    exchange: str
    asset_class: str
    status: str
    tradable: bool
    marginable: bool
    shortable: bool
    easy_to_borrow: bool
    fractionable: bool

    @classmethod
    def of(cls, instrument: Instrument) -> "AssetDetailOut":
        return cls(
            symbol=instrument.symbol,
            name=instrument.name,
            exchange=instrument.exchange,
            asset_class=instrument.asset_class,
            status=instrument.status,
            tradable=instrument.tradable,
            marginable=instrument.marginable,
            shortable=instrument.shortable,
            easy_to_borrow=instrument.easy_to_borrow,
            fractionable=instrument.fractionable,
        )


class QuoteOut(BaseModel):
    symbol: str
    last_trade_price: Decimal | None
    bid_price: Decimal | None
    ask_price: Decimal | None
    bid_size: int | None
    ask_size: int | None
    daily_volume: int | None
    updated_at: datetime | None
    currency: str | None
    source: str
    feed: str
    as_of: datetime | None
    data_age_seconds: int | None
    is_delayed: bool
    is_stale: bool
    served_from_cache: bool

    @classmethod
    def of(cls, view: QuoteView) -> "QuoteOut":
        snapshot = view.snapshot
        freshness = view.freshness
        return cls(
            symbol=view.symbol,
            last_trade_price=snapshot.last_trade_price,
            bid_price=snapshot.bid_price,
            ask_price=snapshot.ask_price,
            bid_size=snapshot.bid_size,
            ask_size=snapshot.ask_size,
            daily_volume=snapshot.daily_volume,
            updated_at=snapshot.quote_updated_at,
            currency=freshness.currency,
            source=freshness.source,
            feed=freshness.feed,
            as_of=freshness.as_of,
            data_age_seconds=freshness.data_age_seconds,
            is_delayed=freshness.is_delayed,
            is_stale=freshness.is_stale,
            served_from_cache=freshness.served_from_cache,
        )


class CandleBarOut(BaseModel):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    @classmethod
    def of(cls, bar: Bar) -> "CandleBarOut":
        return cls(
            timestamp=bar.timestamp,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
        )


class CandlesOut(BaseModel):
    symbol: str
    timeframe: str
    currency: str | None
    source: str
    feed: str
    is_delayed: bool
    bars: list[CandleBarOut]
    next_page_token: str | None

    @classmethod
    def of(cls, view: CandleView) -> "CandlesOut":
        return cls(
            symbol=view.symbol,
            timeframe=view.timeframe,
            currency=view.meta.currency,
            source=view.meta.source,
            feed=view.meta.feed,
            is_delayed=view.meta.is_delayed,
            bars=[CandleBarOut.of(bar) for bar in view.bars],
            next_page_token=view.next_page_token,
        )


class DepthLevelOut(BaseModel):
    bid_price: Decimal | None
    bid_size: int | None
    ask_price: Decimal | None
    ask_size: int | None


class DepthOut(BaseModel):
    symbol: str
    levels: list[DepthLevelOut]
    full_depth_available: bool
    currency: str | None
    source: str
    feed: str
    as_of: datetime | None
    data_age_seconds: int | None
    is_delayed: bool
    is_stale: bool
    served_from_cache: bool

    @classmethod
    def of(cls, view: DepthView) -> "DepthOut":
        return cls(
            symbol=view.symbol,
            levels=[
                DepthLevelOut(
                    bid_price=level.bid_price,
                    bid_size=level.bid_size,
                    ask_price=level.ask_price,
                    ask_size=level.ask_size,
                )
                for level in view.result.levels
            ],
            full_depth_available=view.result.full_depth_available,
            currency=view.freshness.currency,
            source=view.freshness.source,
            feed=view.freshness.feed,
            as_of=view.freshness.as_of,
            data_age_seconds=view.freshness.data_age_seconds,
            is_delayed=view.freshness.is_delayed,
            is_stale=view.freshness.is_stale,
            served_from_cache=view.freshness.served_from_cache,
        )
