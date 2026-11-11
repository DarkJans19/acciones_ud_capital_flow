from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import instrument
from acciones_ud.market_data.adapters.outbound.alpaca.fake_data import FakeAlpacaData
from acciones_ud.market_data.application.candles import CandleService
from acciones_ud.market_data.application.depth import DepthService
from acciones_ud.market_data.application.quotes import QuoteService
from acciones_ud.market_data.domain.entities import (
    Bar,
    BarsPage,
    LatestQuoteDoc,
    QuoteFields,
    Snapshot,
    StoredSnapshot,
)
from acciones_ud.shared.domain.alpaca_errors import AlpacaRateLimited, AlpacaUnavailable
from tests.support.clock import FakeClock
from tests.support.market_fakes import MemoryInstruments, MemorySnapshots, quote_uow

NOW = datetime(2026, 1, 2, 12, tzinfo=UTC)


def current_user() -> CurrentUser:
    return CurrentUser(
        uuid4(),
        uuid4(),
        "ana@example.com",
        "active",
        True,
        frozenset({"investor"}),
        frozenset({"market:read"}),
    )


def build(
    api_settings: Settings,
    instruments: MemoryInstruments,
    snapshots: MemorySnapshots,
    data: FakeAlpacaData,
) -> TestClient:
    app = create_app(api_settings)
    app.dependency_overrides[get_current_user] = current_user
    app.state.quote_service = QuoteService(
        quote_uow(instruments, snapshots), data, FakeClock(NOW), 900
    )
    app.state.candle_service = CandleService(quote_uow(instruments, snapshots), data, "iex")
    app.state.depth_service = DepthService(
        quote_uow(instruments, snapshots), data, FakeClock(NOW), "iex", 900
    )
    return TestClient(app)


def catalog() -> MemoryInstruments:
    return MemoryInstruments([instrument("AAPL", asset_class="us_equity")])


def live_snapshot(feed: str = "iex") -> Snapshot:
    return Snapshot(
        last_trade_price=Decimal("100.5"),
        bid_price=Decimal("100.4"),
        ask_price=Decimal("100.6"),
        bid_size=10,
        ask_size=12,
        daily_volume=1000,
        quote_updated_at=datetime(2026, 1, 2, 11, 59, tzinfo=UTC),
        feed=feed,
    )


def test_quote_returns_live_snapshot_and_stores_it(api_settings: Settings) -> None:
    snapshots = MemorySnapshots()
    data = FakeAlpacaData()
    data.snapshot_value = live_snapshot()
    client = build(api_settings, catalog(), snapshots, data)

    response = client.get("/api/v1/instruments/AAPL/quote")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["served_from_cache"] is False
    assert body["currency"] == "USD"
    assert body["source"] == "alpaca"
    assert body["data_age_seconds"] == 60
    assert snapshots.saves == 1


def test_quote_falls_back_to_the_stored_snapshot(api_settings: Settings) -> None:
    stored = StoredSnapshot(
        snapshot=live_snapshot(), retrieved_at=datetime(2026, 1, 2, 10, tzinfo=UTC)
    )
    data = FakeAlpacaData()
    data.fail("snapshot", AlpacaUnavailable())
    client = build(api_settings, catalog(), MemorySnapshots({"AAPL": stored}), data)

    response = client.get("/api/v1/instruments/AAPL/quote")

    assert response.status_code == 200
    body = response.json()
    assert body["served_from_cache"] is True
    assert body["is_stale"] is True
    assert body["as_of"] == stored.snapshot.quote_updated_at.isoformat().replace("+00:00", "Z")


@pytest.mark.parametrize(
    ("error", "status"),
    [(AlpacaUnavailable(), 502), (AlpacaRateLimited(), 503)],
)
def test_quote_without_snapshot_maps_alpaca_failures(
    api_settings: Settings, error: Exception, status: int
) -> None:
    data = FakeAlpacaData()
    data.fail("snapshot", error)
    client = build(api_settings, catalog(), MemorySnapshots(), data)

    response = client.get("/api/v1/instruments/AAPL/quote")
    assert response.status_code == status


def test_quote_unknown_symbol_skips_alpaca(api_settings: Settings) -> None:
    data = FakeAlpacaData()
    client = build(api_settings, MemoryInstruments(), MemorySnapshots(), data)

    response = client.get("/api/v1/instruments/NOPE/quote")
    assert response.status_code == 404
    assert response.json()["code"] == "SYMBOL_NOT_FOUND"
    assert data.calls == []


def test_delayed_sip_is_marked_delayed(api_settings: Settings) -> None:
    data = FakeAlpacaData()
    data.snapshot_value = live_snapshot(feed="delayed_sip")
    client = build(api_settings, catalog(), MemorySnapshots(), data)

    body = client.get("/api/v1/instruments/AAPL/quote").json()
    assert body["is_delayed"] is True


def test_candles_map_bars_and_pass_the_page_token(api_settings: Settings) -> None:
    data = FakeAlpacaData()
    data.bars_page = BarsPage(
        bars=[
            Bar(
                timestamp=datetime(2026, 1, 2, 15, tzinfo=UTC),
                open=Decimal("1"),
                high=Decimal("2"),
                low=Decimal("1"),
                close=Decimal("2"),
                volume=10,
            ),
            Bar(
                timestamp=datetime(2026, 1, 2, 16, tzinfo=UTC),
                open=Decimal("2"),
                high=Decimal("3"),
                low=Decimal("2"),
                close=Decimal("3"),
                volume=20,
            ),
        ],
        next_page_token="next-token",
    )
    client = build(api_settings, catalog(), MemorySnapshots(), data)

    response = client.get(
        "/api/v1/instruments/AAPL/candles",
        params={
            "timeframe": "1Hour",
            "start": "2026-01-02",
            "end": "2026-01-02",
            "page_token": "current-token",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["timeframe"] == "1Hour"
    assert body["next_page_token"] == "next-token"
    assert [item["close"] for item in body["bars"]] == ["2", "3"]


def test_candles_reject_unknown_timeframe_before_alpaca(api_settings: Settings) -> None:
    data = FakeAlpacaData()
    client = build(api_settings, catalog(), MemorySnapshots(), data)

    response = client.get(
        "/api/v1/instruments/AAPL/candles",
        params={"timeframe": "7Min", "start": "2026-01-02", "end": "2026-01-03"},
    )
    assert response.status_code == 422
    assert data.calls == []


def test_depth_one_sided_quote_keeps_missing_values_null(api_settings: Settings) -> None:
    data = FakeAlpacaData()
    data.quote_value = LatestQuoteDoc(
        quote=QuoteFields(
            bid_price=None,
            bid_size=None,
            ask_price=Decimal("100.5"),
            ask_size=5,
            timestamp=datetime(2026, 1, 2, 11, 59, tzinfo=UTC),
        )
    )
    client = build(api_settings, catalog(), MemorySnapshots(), data)

    response = client.get("/api/v1/instruments/AAPL/depth")
    assert response.status_code == 200
    body = response.json()
    assert body["levels"] == [
        {"bid_price": None, "bid_size": None, "ask_price": "100.5", "ask_size": 5}
    ]
    assert body["full_depth_available"] is False
    assert body["served_from_cache"] is False


def test_depth_without_quote_object_returns_no_levels(api_settings: Settings) -> None:
    data = FakeAlpacaData()
    data.quote_value = LatestQuoteDoc(quote=None)
    client = build(api_settings, catalog(), MemorySnapshots(), data)

    body = client.get("/api/v1/instruments/AAPL/depth").json()
    assert body["levels"] == []


def test_depth_rejects_invalid_and_unknown_symbols_before_alpaca(
    api_settings: Settings,
) -> None:
    data = FakeAlpacaData()
    client = build(api_settings, MemoryInstruments(), MemorySnapshots(), data)

    assert client.get("/api/v1/instruments/BAD$X/depth").status_code == 422
    assert client.get("/api/v1/instruments/NOPE/depth").status_code == 404
    assert data.calls == []


def test_depth_failure_maps_to_502_without_writing(api_settings: Settings) -> None:
    data = FakeAlpacaData()
    data.fail("latest_quote", AlpacaUnavailable())
    snapshots = MemorySnapshots()
    client = build(api_settings, catalog(), snapshots, data)

    response = client.get("/api/v1/instruments/AAPL/depth")
    assert response.status_code == 502
    assert snapshots.saves == 0
