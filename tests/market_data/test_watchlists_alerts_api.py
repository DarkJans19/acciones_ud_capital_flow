from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import instrument
from acciones_ud.market_data.application.alerts import AlertService
from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.application.watchlists import WatchlistService
from acciones_ud.market_data.domain.entities import Watchlist
from acciones_ud.market_data.domain.watchlists import SYMBOL_LIMIT, WATCHLIST_LIMIT
from tests.support.clock import FakeClock
from tests.support.market_fakes import (
    MemoryAlerts,
    MemoryInstruments,
    MemoryNotifications,
    MemoryWatchlists,
    RecordingSender,
    alert_uow,
    notification_uow,
    watchlist_uow,
)

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def build(
    api_settings: Settings,
    *,
    premium: bool = True,
    user_id: object | None = None,
) -> tuple[
    TestClient,
    MemoryInstruments,
    MemoryWatchlists,
    MemoryAlerts,
    MemoryNotifications,
    object,
]:
    app = create_app(api_settings)
    current_id = user_id or uuid4()
    user = CurrentUser(
        current_id,  # type: ignore[arg-type]
        uuid4(),
        "ana@example.com",
        "active",
        premium,
        frozenset({"investor"}),
        frozenset({"market:read", "watchlist:manage"}),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    instruments = MemoryInstruments([instrument("AAPL"), instrument("MSFT")])
    watchlists = MemoryWatchlists()
    alerts = MemoryAlerts()
    notifications = MemoryNotifications()
    app.state.watchlist_service = WatchlistService(
        watchlist_uow(instruments, watchlists), FakeClock(NOW)
    )
    app.state.alert_service = AlertService(alert_uow(instruments, alerts), FakeClock(NOW))
    app.state.notifier = Notifier(
        notification_uow(notifications), [RecordingSender("email")], FakeClock(NOW)
    )
    return TestClient(app), instruments, watchlists, alerts, notifications, current_id


def test_non_premium_is_rejected(api_settings: Settings) -> None:
    client, *_ = build(api_settings, premium=False)
    response = client.get("/api/v1/watchlists")
    assert response.status_code == 403
    assert response.json()["code"] == "PREMIUM_REQUIRED"


def test_watchlist_lifecycle_and_duplicates(api_settings: Settings) -> None:
    client, *_ = build(api_settings)

    created = client.post("/api/v1/watchlists", json={"name": " Tech "})
    assert created.status_code == 201
    watchlist_id = created.json()["id"]
    assert created.json()["name"] == "Tech"

    added = client.post(
        f"/api/v1/watchlists/{watchlist_id}/items", json={"symbol": "aapl"}
    )
    assert added.status_code == 200
    assert added.json()["symbols"] == ["AAPL"]

    duplicate = client.post(
        f"/api/v1/watchlists/{watchlist_id}/items", json={"symbol": "AAPL"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "SYMBOL_ALREADY_IN_WATCHLIST"

    unknown = client.post(
        f"/api/v1/watchlists/{watchlist_id}/items", json={"symbol": "NOPE"}
    )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "SYMBOL_NOT_FOUND"

    removed = client.delete(f"/api/v1/watchlists/{watchlist_id}/items/AAPL")
    assert removed.status_code == 200
    assert removed.json()["symbols"] == []


def test_watchlist_limits(api_settings: Settings) -> None:
    client, _, watchlists, _, _, current_id = build(api_settings)
    for index in range(WATCHLIST_LIMIT):
        watchlist_id = uuid4()
        watchlists.items[watchlist_id] = Watchlist(
            id=watchlist_id, name=f"list-{index}", symbols=[]
        )
        watchlists.owners[watchlist_id] = current_id
    response = client.post("/api/v1/watchlists", json={"name": "one too many"})
    assert response.status_code == 422

    client2, _, watchlists2, _, _, current_id2 = build(api_settings)
    watchlist_id = uuid4()
    watchlists2.items[watchlist_id] = Watchlist(
        id=watchlist_id,
        name="full",
        symbols=[f"S{index}" for index in range(SYMBOL_LIMIT)],
    )
    watchlists2.owners[watchlist_id] = current_id2
    response = client2.post(
        f"/api/v1/watchlists/{watchlist_id}/items", json={"symbol": "AAPL"}
    )
    assert response.status_code == 422


def test_watchlist_ownership_is_a_404(api_settings: Settings) -> None:
    client, _, watchlists, _, _, current_id = build(api_settings)
    foreign_id = uuid4()
    watchlists.items[foreign_id] = Watchlist(id=foreign_id, name="other", symbols=[])
    watchlists.owners[foreign_id] = uuid4()

    response = client.get(f"/api/v1/watchlists/{foreign_id}")
    assert response.status_code == 404
    assert response.json()["details"]["resource"] == "watchlist"


def test_alert_lifecycle(api_settings: Settings) -> None:
    client, *_ = build(api_settings)

    created = client.post(
        "/api/v1/price-alerts",
        json={"symbol": "AAPL", "comparator": "above", "threshold": "150.00"},
    )
    assert created.status_code == 201
    alert_id = created.json()["id"]
    assert created.json()["status"] == "active"

    deactivated = client.post(f"/api/v1/price-alerts/{alert_id}/deactivate")
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "inactive"

    activated = client.post(f"/api/v1/price-alerts/{alert_id}/activate")
    assert activated.json()["status"] == "active"

    assert client.get("/api/v1/price-alerts").json()[0]["id"] == alert_id
    assert client.delete(f"/api/v1/price-alerts/{alert_id}").status_code == 204
    assert client.get("/api/v1/price-alerts").json() == []


def test_alert_validation_and_unknown_symbol(api_settings: Settings) -> None:
    client, *_ = build(api_settings)

    unknown = client.post(
        "/api/v1/price-alerts",
        json={"symbol": "NOPE", "comparator": "above", "threshold": "10"},
    )
    assert unknown.status_code == 404

    zero = client.post(
        "/api/v1/price-alerts",
        json={"symbol": "AAPL", "comparator": "above", "threshold": "0"},
    )
    assert zero.status_code == 422

    bad_comparator = client.post(
        "/api/v1/price-alerts",
        json={"symbol": "AAPL", "comparator": "equals", "threshold": "10"},
    )
    assert bad_comparator.status_code == 422


def test_notifications_listing_and_page_size(api_settings: Settings) -> None:
    client, _, _, _, notifications, current_id = build(api_settings)
    notifier = client.app.state.notifier

    import asyncio

    from acciones_ud.market_data.domain.entities import Recipient

    asyncio.run(
        notifier.notify(
            [Recipient(user_id=current_id, channels=frozenset({"in_app"}))],  # type: ignore[arg-type]
            "price_changes",
            {"symbol": "AAPL", "threshold": "10"},
        )
    )
    listed = client.get("/api/v1/notifications").json()
    assert len(listed) == 1
    assert listed[0]["event_type"] == "price_changes"
    assert notifications.deliveries[
        (notifications.items[0].id, "in_app")
    ][0] == "sent"
    assert client.get("/api/v1/notifications", params={"page_size": 0}).status_code == 422
