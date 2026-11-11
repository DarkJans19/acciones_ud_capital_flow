# Feature: identity-market-backend, Property 38: Quote fallback decision

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import instrument
from acciones_ud.market_data.adapters.outbound.alpaca.fake_data import FakeAlpacaData
from acciones_ud.market_data.application.quotes import QuoteService, QuoteView
from acciones_ud.market_data.domain.entities import Snapshot, StoredSnapshot
from acciones_ud.shared.domain.alpaca_errors import AlpacaRateLimited, AlpacaUnavailable
from acciones_ud.shared.domain.errors import AppError
from tests.support.clock import FakeClock
from tests.support.market_fakes import MemoryInstruments, MemorySnapshots, quote_uow

NOW = datetime(2026, 1, 2, 12, tzinfo=UTC)
INSTANTS = st.one_of(
    st.none(),
    st.datetimes(
        min_value=datetime(2026, 1, 1), max_value=datetime(2026, 1, 3), timezones=st.just(UTC)
    ),
)
PRICES = st.one_of(
    st.none(), st.decimals(min_value=Decimal("0"), max_value=Decimal("1000"), places=4)
)
FEEDS = st.sampled_from(["iex", "sip", "delayed_sip"])
SNAPSHOTS = st.builds(
    Snapshot,
    last_trade_price=PRICES,
    bid_price=PRICES,
    ask_price=PRICES,
    bid_size=st.one_of(st.none(), st.integers(min_value=0, max_value=10_000)),
    ask_size=st.one_of(st.none(), st.integers(min_value=0, max_value=10_000)),
    daily_volume=st.one_of(st.none(), st.integers(min_value=0, max_value=10_000_000)),
    quote_updated_at=INSTANTS,
    feed=FEEDS,
)
FAILURES = st.sampled_from([None, "unavailable", "rate_limited"])


def stored_strategy() -> st.SearchStrategy[StoredSnapshot | None]:
    return st.one_of(
        st.none(),
        st.builds(
            StoredSnapshot,
            snapshot=SNAPSHOTS,
            retrieved_at=st.datetimes(
                min_value=datetime(2026, 1, 1),
                max_value=datetime(2026, 1, 3),
                timezones=st.just(UTC),
            ),
        ),
    )


@given(live=SNAPSHOTS, failure=FAILURES, stored=stored_strategy())
def test_quote_fallback_decision(
    live: Snapshot, failure: str | None, stored: StoredSnapshot | None
) -> None:
    instruments = MemoryInstruments([instrument("AAPL")])
    snapshots = MemorySnapshots({"AAPL": stored} if stored is not None else {})
    data = FakeAlpacaData()
    data.snapshot_value = live
    if failure == "unavailable":
        data.fail("snapshot", AlpacaUnavailable())
    elif failure == "rate_limited":
        data.fail("snapshot", AlpacaRateLimited())
    service = QuoteService(
        quote_uow(instruments, snapshots), data, FakeClock(NOW), threshold_seconds=900
    )
    before = {symbol: value for symbol, value in snapshots.items.items()}

    async def run() -> QuoteView | AppError:
        try:
            return await service.quote("AAPL")
        except AppError as error:
            return error

    outcome = asyncio.run(run())
    after = snapshots.items

    if failure is None:
        entry = after["AAPL"]
        assert isinstance(outcome, QuoteView)
        assert entry.snapshot == live
        assert snapshots.saves == 1
        assert outcome.freshness.served_from_cache is False
        return

    if stored is not None:
        assert after == before
        assert snapshots.saves == 0
        assert isinstance(outcome, QuoteView)
        assert outcome.snapshot == stored.snapshot
        assert outcome.freshness.as_of == stored.snapshot.quote_updated_at
        assert outcome.freshness.is_stale is True
        assert outcome.freshness.served_from_cache is True
        return

    assert after == before
    assert isinstance(outcome, AppError)
    expected = 502 if failure == "unavailable" else 503
    assert outcome.status == expected


def test_quote_without_catalog_symbol_sends_no_alpaca_request() -> None:
    data = FakeAlpacaData()
    service = QuoteService(
        quote_uow(MemoryInstruments(), MemorySnapshots()), data, FakeClock(NOW), 900
    )

    with pytest.raises(AppError) as error:
        asyncio.run(service.quote("NOPE"))
    assert error.value.status == 404
    assert data.calls == []
