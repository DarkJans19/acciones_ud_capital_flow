"""Executable security expectations, xfail STRICT until their finding is resolved.

Run with --runxfail to see actual failures. Mocks are explicit, never a live attack.
"""

from json import JSONDecodeError
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from acciones_ud.admin.application.commission_service import CommissionQuoteService
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.application.login import AuthService
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.market_data.adapters.inbound.http.routers import stream as stream_router
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.admin.fakes import Markets, setup
from tests.market_data.test_stream_api import make_app


@pytest.mark.xfail(strict=True, reason="AUD-01: PATCH absent from CORS allow_methods")
def test_profile_patch_preflight_is_allowed(api_settings):
    client = TestClient(create_app(api_settings))
    response = client.options(
        "/api/v1/users/me",
        headers={
            "Origin": "https://frontend.test",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "body",
    [
        {"email": "", "password": "ValidPassword123"},
        {"email": "not-an-email", "password": "ValidPassword123"},
        {"email": "a" * 255 + "@example.com", "password": "ValidPassword123"},
        {"email": "user@example.com", "password": ""},
    ],
    ids=["empty-email", "invalid-email", "oversize-email", "empty-password"],
)
@pytest.mark.xfail(strict=True, reason="AUD-02: login violates requirement 3.11")
def test_invalid_login_never_reaches_credential_verification(api_settings, body):
    class AuthSpy(AuthService):
        def __init__(self):
            self.calls = 0

        async def login(self, *args, **kwargs):
            self.calls += 1
            raise AppError(401, ErrorCode.INVALID_CREDENTIALS, "Invalid credentials.")

    app = create_app(api_settings)
    spy = AuthSpy()
    app.state.auth_service = spy
    response = TestClient(app).post("/api/v1/auth/login", json=body)
    assert (response.status_code, spy.calls) == (422, 0)


@pytest.mark.parametrize("qty,price", [("1e100", "1"), ("1", "1e100"), ("1e999999", "1")])
@pytest.mark.xfail(strict=True, reason="AUD-03: unbounded quote decimals cause HTTP 500")
def test_extreme_commission_input_is_a_client_error(api_settings, qty, price):
    uow, clock, actor, _ = setup()
    app = create_app(api_settings)
    app.state.admin_quote = CommissionQuoteService(uow, Markets(), clock)
    user = CurrentUser(
        actor, uuid4(), "audit@example.com", "active", False, frozenset({"investor"})
    )
    app.dependency_overrides[get_current_user] = lambda: user
    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/commissions/quote",
        params={"symbol": "AAPL", "side": "buy", "qty": qty, "price": price},
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("payload", ["[]", "null", "1", '"text"', "{"])
@pytest.mark.xfail(strict=True, reason="AUD-04: malformed WS frame escapes the protocol loop")
def test_websocket_invalid_frame_is_handled_without_uncaught_exception(
    api_settings, monkeypatch, payload
):
    settings = api_settings.model_copy(update={"price_streaming_enabled": "true"})
    app, _ = make_app(settings, monkeypatch)
    client = TestClient(app)
    client.cookies.set("access_token", "fixture-cookie")
    # Controlled close (1003/1007/1008) or a protocol error are both acceptable.
    try:
        with client.websocket_connect("/ws/v1/market-feed") as ws:
            ws.send_text(payload)
            try:
                reply = ws.receive_json()
            except WebSocketDisconnect as exc:
                assert exc.code in {1003, 1007, 1008}
            else:
                assert reply.get("type") == "error"
    except (AttributeError, JSONDecodeError):
        pytest.fail("unhandled WebSocket frame parsing exception", pytrace=False)


@pytest.mark.xfail(strict=True, reason="AUD-05: WebSocket authorization checked only at handshake")
def test_websocket_revoked_session_cannot_resubscribe(api_settings, monkeypatch):
    settings = api_settings.model_copy(update={"price_streaming_enabled": "true"})
    app, _ = make_app(settings, monkeypatch)
    client = TestClient(app)
    client.cookies.set("access_token", "fixture-cookie")
    calls = []
    revoked = False

    async def authenticated(token, request):
        calls.append(token)
        if revoked:
            raise AppError(401, ErrorCode.NOT_AUTHENTICATED, "Session revoked.")
        return CurrentUser(
            uuid4(), uuid4(), "audit@example.com", "active", False,
            frozenset({"investor"}), frozenset({"market:read"}),
        )

    monkeypatch.setattr(stream_router, "authenticate_access_token", authenticated)
    with client.websocket_connect("/ws/v1/market-feed") as ws:
        revoked = True
        ws.send_json({"action": "subscribe", "symbols": ["AAPL"]})
        try:
            reply = ws.receive_json()
        except WebSocketDisconnect as exc:
            assert exc.code == 1008
        else:
            assert reply.get("type") != "subscribed", reply


@pytest.mark.xfail(strict=True, reason="AUD-06: password endpoint has no application throttling")
async def test_login_has_a_bounded_attempt_budget(api_settings):
    class AuthSpy(AuthService):
        def __init__(self):
            pass

        async def login(self, *args, **kwargs):
            raise AppError(401, ErrorCode.INVALID_CREDENTIALS, "Invalid credentials.")

    app = create_app(api_settings)
    app.state.auth_service = AuthSpy()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://audit.test"
    ) as client:
        statuses = [
            (await client.post(
                "/api/v1/auth/login",
                json={"email": "audit@example.com", "password": "WrongPassword123"},
            )).status_code
            for _ in range(30)
        ]
    assert 429 in statuses, statuses
