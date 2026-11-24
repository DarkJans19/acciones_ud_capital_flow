"""RF-03/43..47: deterministic complement to the existing random role property."""

from dataclasses import replace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from tests.admin.api.test_access_control import PERIOD, PERMISSIONS, ROUTES, ServiceSpy


@pytest.mark.parametrize("role", list(PERMISSIONS))
@pytest.mark.parametrize("session", ["valid", "missing", "inactive", "permission_removed"])
def test_every_admin_route_against_every_role_and_session(api_settings, role, session):
    app = create_app(api_settings)
    spy = ServiceSpy()
    for name in (
        "admin_fees", "admin_quote", "admin_commissions", "admin_markets", "admin_halts",
        "admin_dispatcher", "admin_trail", "admin_restrictions", "admin_compliance", "admin_kpis",
    ):
        setattr(app.state, name, spy)
    user = CurrentUser(
        UUID(int=100), UUID(int=200), "audit@example.com", "active", False,
        frozenset({role}), frozenset(PERMISSIONS[role]),
    )
    if session == "inactive":
        user = replace(user, account_status="pending_broker_activation")
    if session == "permission_removed":
        user = replace(user, permissions=frozenset())
    if session != "missing":
        app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    for method, path, permission, body in ROUTES:
        spy.calls = 0
        allowed = session != "missing" and (
            permission == "authenticated" or user.account_status == "active" and (
                permission in user.permissions
                or permission == "trader" and role in {"investor", "broker"}
                or permission == role
            )
        )
        response = client.request(
            method, "/api/v1" + path, json=body,
            params={**PERIOD, "symbol": "AAPL", "side": "buy", "qty": "1", "price": "10"},
        )
        expected = 401 if session == "missing" else 418 if allowed else 403
        assert response.status_code == expected, (role, session, method, path, response.text)
        assert spy.calls == int(allowed)
