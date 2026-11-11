from datetime import time
from uuid import uuid4

from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import (
    FakeAlpacaBrokerMarket,
    calendar_session,
)
from acciones_ud.market_data.application.calendar import (
    CalendarService,
    ClockService,
    MarketStatusService,
)
from acciones_ud.market_data.application.schedule_admin import ScheduleAdminService
from acciones_ud.market_data.domain.entities import Market
from tests.support.market_fakes import MemoryMarkets, market_uow

MARKET = Market(
    code="NYSE",
    name="New York Stock Exchange",
    default_open_time=time(9, 30),
    default_close_time=time(16),
)


def build(
    api_settings: Settings, markets: MemoryMarkets, broker: FakeAlpacaBrokerMarket
) -> TestClient:
    app = create_app(api_settings)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        uuid4(),
        uuid4(),
        "admin@example.com",
        "active",
        True,
        frozenset({"administrator"}),
        frozenset({"market:read", "admin:markets"}),
    )
    app.state.calendar_service = CalendarService(market_uow(markets), broker)
    app.state.market_status_service = MarketStatusService(market_uow(markets), broker)
    app.state.clock_service = ClockService(broker)
    app.state.schedule_admin_service = ScheduleAdminService(market_uow(markets))
    return TestClient(app)


def broker() -> FakeAlpacaBrokerMarket:
    fake = FakeAlpacaBrokerMarket()
    fake.sessions = [
        calendar_session("2026-01-02"),
        calendar_session("2026-01-05"),
    ]
    return fake


def test_calendar_expands_every_date(api_settings: Settings) -> None:
    client = build(api_settings, MemoryMarkets([MARKET]), broker())

    response = client.get(
        "/api/v1/markets/calendar",
        params={"start": "2026-01-02", "end": "2026-01-05"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["time_zone"] == "America/New_York"
    assert [day["kind"] for day in body["days"]] == [
        "trading_day",
        "weekend",
        "weekend",
        "trading_day",
    ]
    assert body["days"][0]["open_at"].startswith("2026-01-02T09:30:00")
    assert body["days"][1]["open_at"] is None


def test_calendar_uses_market_defaults_and_overrides(api_settings: Settings) -> None:
    markets = MemoryMarkets([MARKET])
    client = build(api_settings, markets, broker())

    created = client.post(
        "/api/v1/admin/markets/NYSE/schedule-overrides",
        json={"date": "2026-01-02", "closed": False, "open_time": "10:00", "close_time": "14:00"},
    )
    assert created.status_code == 201

    calendar = client.get(
        "/api/v1/markets/calendar",
        params={"start": "2026-01-02", "end": "2026-01-02", "market": "NYSE"},
    ).json()
    assert calendar["days"][0]["override"] is True
    assert calendar["days"][0]["open_at"].startswith("2026-01-02T10:00:00")


def test_market_status_matches_calendar(api_settings: Settings) -> None:
    client = build(api_settings, MemoryMarkets([MARKET]), broker())
    response = client.get(
        "/api/v1/markets/NYSE/status", params={"date": "2026-01-02"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["market"] == "NYSE"
    assert body["open"] is True
    assert body["override"] is False


def test_clock_converts_to_requested_zone(api_settings: Settings) -> None:
    client = build(api_settings, MemoryMarkets([MARKET]), broker())
    response = client.get("/api/v1/markets/clock", params={"tz": "UTC"})
    assert response.status_code == 200
    assert response.json()["time_zone"] == "UTC"
    assert response.json()["next_open"].startswith("2024-01-02T14:30:00")


def test_unknown_market_and_invalid_tz(api_settings: Settings) -> None:
    client = build(api_settings, MemoryMarkets([MARKET]), broker())
    response = client.get(
        "/api/v1/markets/calendar",
        params={"start": "2026-01-02", "end": "2026-01-02", "market": "X"},
    )
    assert response.status_code == 404
    assert (
        client.get("/api/v1/markets/clock", params={"tz": "Mars/Olympus"}).status_code == 422
    )


def test_schedule_admin_lifecycle(api_settings: Settings) -> None:
    markets = MemoryMarkets([MARKET])
    client = build(api_settings, markets, broker())

    updated = client.put(
        "/api/v1/admin/markets/NYSE/default-schedule",
        json={"open_time": "09:00", "close_time": "15:00"},
    )
    assert updated.status_code == 200
    assert updated.json()["open_time"] == "09:00:00"

    deleted = client.delete("/api/v1/admin/markets/NYSE/default-schedule")
    assert deleted.status_code == 204
    assert markets.items["NYSE"].default_open_time is None

    payload = {"date": "2026-01-02", "closed": True}
    first = client.post("/api/v1/admin/markets/NYSE/schedule-overrides", json=payload)
    assert first.status_code == 201
    duplicate = client.post("/api/v1/admin/markets/NYSE/schedule-overrides", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "OVERRIDE_EXISTS"

    override_id = first.json()["id"]
    updated_override = client.put(
        f"/api/v1/admin/markets/NYSE/schedule-overrides/{override_id}",
        json={"closed": False, "open_time": "10:00", "close_time": "12:00"},
    )
    assert updated_override.status_code == 200
    assert updated_override.json()["closed"] is False

    listed = client.get("/api/v1/admin/markets/NYSE/schedule-overrides")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    removed = client.delete(f"/api/v1/admin/markets/NYSE/schedule-overrides/{override_id}")
    assert removed.status_code == 204
    assert (
        client.delete(f"/api/v1/admin/markets/NYSE/schedule-overrides/{override_id}").status_code
        == 404
    )


def test_schedule_validation_and_unknown_market(api_settings: Settings) -> None:
    client = build(api_settings, MemoryMarkets([MARKET]), broker())

    invalid = client.post(
        "/api/v1/admin/markets/NYSE/schedule-overrides",
        json={"date": "2026-01-02", "closed": True, "open_time": "10:00"},
    )
    assert invalid.status_code == 422

    unknown = client.post(
        "/api/v1/admin/markets/X/schedule-overrides",
        json={"date": "2026-01-02", "closed": True},
    )
    assert unknown.status_code == 404
    assert unknown.json()["details"]["resource"] == "market"
