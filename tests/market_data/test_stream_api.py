"""WebSocket market feed: rejection keeps the previous subscription (13.10, 14.13)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from acciones_ud.config.settings import Settings
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.market_data.adapters.inbound.http.routers import stream as stream_router
from acciones_ud.market_data.application.stream_hub import StreamHub
from acciones_ud.market_data.domain.streaming import SubscriptionRegistry

CATALOG = {"AAPL", "MSFT"}


class StubUpstream:
    def __init__(self) -> None:
        self.requested: set[str] = set()
        self.closed = False

    async def subscribe(self, symbols: set[str]) -> None:
        self.requested = set(symbols)

    async def stream(self):  # pragma: no cover - the hub is never started here
        if False:
            yield

    async def close(self) -> None:
        self.closed = True


def make_app(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> tuple[object, StreamHub]:
    app = create_app(settings)
    hub = StreamHub(SubscriptionRegistry(), StubUpstream(), catalog_symbols)
    app.state.stream_hub = hub
    user = CurrentUser(
        uuid4(),
        uuid4(),
        "ana@example.com",
        "active",
        True,
        frozenset({"investor"}),
        frozenset({"market:read"}),
    )

    async def authenticated(token: str, request: object) -> CurrentUser:
        return user

    monkeypatch.setattr(stream_router, "authenticate_access_token", authenticated)
    return app, hub


async def catalog_symbols() -> set[str]:
    return set(CATALOG)


def test_invalid_subscription_keeps_the_previous_one(
    api_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = api_settings.model_copy(update={"price_streaming_enabled": "true"})
    app, hub = make_app(settings, monkeypatch)
    client = TestClient(app)
    client.cookies.set("access_token", "token")

    with client.websocket_connect("/ws/v1/market-feed") as websocket:
        websocket.send_json({"action": "subscribe", "symbols": ["AAPL"]})
        assert websocket.receive_json() == {"type": "subscribed", "symbols": ["AAPL"]}
        client_id = next(iter(hub.sockets))

        websocket.send_json({"action": "subscribe", "symbols": ["NOPE"]})
        assert websocket.receive_json() == {
            "type": "error",
            "code": "INVALID_SUBSCRIPTION",
        }
        assert hub.registry.symbols(client_id) == {"AAPL"}


def test_unknown_action_keeps_the_previous_subscription(
    api_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = api_settings.model_copy(update={"price_streaming_enabled": "true"})
    app, hub = make_app(settings, monkeypatch)
    client = TestClient(app)
    client.cookies.set("access_token", "token")

    with client.websocket_connect("/ws/v1/market-feed") as websocket:
        websocket.send_json({"action": "subscribe", "symbols": ["AAPL"]})
        websocket.receive_json()
        client_id = next(iter(hub.sockets))

        websocket.send_json({"action": "unsubscribe"})
        assert websocket.receive_json() == {"type": "error", "code": "UNKNOWN_ACTION"}
        assert hub.registry.symbols(client_id) == {"AAPL"}


def test_disabled_streaming_closes_the_socket(api_settings: Settings) -> None:
    app = create_app(api_settings)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect("/ws/v1/market-feed"):
            pass

    assert caught.value.code == 1008
