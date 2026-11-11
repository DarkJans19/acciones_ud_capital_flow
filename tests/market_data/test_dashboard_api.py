from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import (
    FakeAlpacaBrokerMarket,
    instrument,
)
from acciones_ud.market_data.adapters.outbound.alpaca.fake_data import FakeAlpacaData
from acciones_ud.market_data.application.dashboard import DashboardService
from acciones_ud.market_data.domain.entities import Snapshot
from acciones_ud.shared.domain.alpaca_errors import AlpacaUnavailable
from tests.support.market_fakes import (
    MemoryInstruments,
    MemoryProfiles,
    dashboard_uow,
)


def build(
    api_settings: Settings,
    instruments: MemoryInstruments,
    profiles: MemoryProfiles,
    data: FakeAlpacaData,
    broker: FakeAlpacaBrokerMarket,
) -> TestClient:
    app = create_app(api_settings)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        uuid4(),
        uuid4(),
        "ana@example.com",
        "active",
        True,
        frozenset({"investor"}),
        frozenset({"market:read"}),
    )
    app.state.dashboard_service = DashboardService(
        dashboard_uow(instruments, profiles), data, broker, ["MSFT", "AAPL"]
    )
    return TestClient(app)


def snapshot(price: str) -> Snapshot:
    return Snapshot(
        last_trade_price=Decimal(price),
        quote_updated_at=datetime(2026, 1, 2, 12, tzinfo=UTC),
    )


def test_dashboard_matches_interests(api_settings: Settings) -> None:
    instruments = MemoryInstruments(
        [
            instrument("AAPL", sector="Technology"),
            instrument("MSFT", sector="Energy"),
        ]
    )
    profiles = MemoryProfiles(["technology"], "beginner")
    data = FakeAlpacaData()
    data.snapshots_value = {"AAPL": snapshot("100")}
    client = build(api_settings, instruments, profiles, data, FakeAlpacaBrokerMarket())

    body = client.get("/api/v1/dashboard").json()
    assert body["source"] == "interests"
    assert body["level"] == "beginner"
    assert body["beginner"] is True
    assert [item["symbol"] for item in body["instruments"]] == ["AAPL"]
    assert body["instruments"][0]["price"] == "100"
    assert body["market_status"] == "open"


def test_dashboard_falls_back_to_defaults(api_settings: Settings) -> None:
    instruments = MemoryInstruments([instrument("AAPL"), instrument("MSFT")])
    data = FakeAlpacaData()
    data.snapshots_value = {"AAPL": snapshot("100")}
    client = build(
        api_settings, instruments, MemoryProfiles(), data, FakeAlpacaBrokerMarket()
    )

    body = client.get("/api/v1/dashboard").json()
    assert body["source"] == "default"
    assert [item["symbol"] for item in body["instruments"]] == ["AAPL", "MSFT"]
    assert body["instruments"][0]["quote_unavailable"] is False
    assert body["instruments"][1]["quote_unavailable"] is True
    assert body["instruments"][1]["price"] is None


def test_dashboard_degrades_on_quote_and_clock_failures(api_settings: Settings) -> None:
    instruments = MemoryInstruments([instrument("AAPL")])
    data = FakeAlpacaData()
    data.fail("snapshots", AlpacaUnavailable())
    broker = FakeAlpacaBrokerMarket()
    broker.fail("clock", AlpacaUnavailable())
    client = build(api_settings, instruments, MemoryProfiles(), data, broker)

    body = client.get("/api/v1/dashboard").json()
    assert body["market_status"] is None
    assert body["market_status_unavailable"] is True
    assert body["instruments"][0]["quote_unavailable"] is True
