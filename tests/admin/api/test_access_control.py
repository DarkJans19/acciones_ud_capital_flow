from dataclasses import replace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.shared.domain.errors import AppError, ErrorCode

IDENT = str(UUID(int=1))
PERIOD = {"from": "2026-11-01", "to": "2026-11-20"}
DECISION = {"reason": "Approved", "totp_code": "123456"}
ROUTES = [
    ("GET", "/admin/fee-schedules", "admin:fees", None),
    ("GET", "/admin/fee-schedules/default/versions", "admin:fees", None),
    (
        "POST",
        "/admin/fee-schedules/default/versions",
        "admin:fees",
        {
            **DECISION,
            "commission_rate_pct": "2",
            "platform_share_pct": "60",
            "expected_latest_version": 1,
        },
    ),
    ("POST", f"/admin/fee-schedules/default/versions/{IDENT}/cancel", "admin:fees", DECISION),
    ("GET", "/commissions/quote?symbol=AAPL&side=buy&qty=1&price=10", "trader", None),
    ("GET", "/commissions", "investor", None),
    ("GET", "/broker/commissions", "broker", None),
    ("GET", "/admin/commissions", "admin:commissions", None),
    ("GET", "/admin/markets", "admin:markets", None),
    ("GET", "/admin/markets/NASDAQ", "admin:markets", None),
    ("GET", "/admin/markets/NASDAQ/schedule-changes", "admin:markets", None),
    ("POST", "/admin/trading-halts", "admin:halts", {**DECISION, "scope": "global"}),
    ("POST", f"/admin/trading-halts/{IDENT}/release", "admin:halts", DECISION),
    ("GET", "/admin/trading-halts", "admin:halts", None),
    ("GET", "/trading-halts/active", "authenticated", None),
    ("GET", "/admin/audit-trail", "admin:audit", None),
    ("GET", f"/admin/audit-trail/orders/{IDENT}", "admin:audit", None),
    ("POST", "/admin/compliance/restrictions", "admin:compliance", {**DECISION, "user_id": IDENT}),
    ("POST", f"/admin/compliance/restrictions/{IDENT}/lift", "admin:compliance", DECISION),
    ("GET", "/admin/compliance/restrictions", "admin:compliance:read", None),
    ("GET", "/admin/compliance/atypical-operations", "admin:compliance:read", None),
    ("POST", f"/admin/compliance/users/{IDENT}/audit-reports", "admin:compliance", PERIOD),
    ("GET", f"/admin/compliance/audit-reports/{IDENT}", "admin:compliance:read", None),
    ("GET", f"/admin/compliance/users/{IDENT}/audit-reports", "admin:compliance:read", None),
    ("GET", "/admin/kpis", "admin:bi", None),
]
PERMISSIONS = {
    "administrator": {
        "admin:fees",
        "admin:commissions",
        "admin:markets",
        "admin:halts",
        "admin:audit",
        "admin:compliance",
        "admin:compliance:read",
        "admin:bi",
    },
    "auditor": {"admin:audit", "admin:compliance:read"},
    "analyst": {"admin:bi"},
    "investor": set(),
    "broker": set(),
}


class ServiceSpy:
    def __init__(self):
        self.calls = 0

    def __getattr__(self, name):
        async def call(*args, **kwargs):
            self.calls += 1
            raise AppError(418, ErrorCode.HTTP_ERROR, "Authorized service reached")

        return call


# Feature: admin-mod-07, Property 17: Control de acceso de los endpoints
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    st.integers(0, len(ROUTES) - 1),
    st.sampled_from(list(PERMISSIONS)),
    st.sampled_from(["valid", "missing", "inactive", "permission_removed"]),
)
def test_endpoint_access_matrix(api_settings, index, role, session):
    app = create_app(api_settings)
    spy = ServiceSpy()
    for name in (
        "admin_fees",
        "admin_quote",
        "admin_commissions",
        "admin_markets",
        "admin_halts",
        "admin_dispatcher",
        "admin_trail",
        "admin_restrictions",
        "admin_compliance",
        "admin_kpis",
    ):
        setattr(app.state, name, spy)
    user = CurrentUser(
        UUID(int=100),
        UUID(int=200),
        "user@test",
        "active",
        False,
        frozenset({role}),
        frozenset(PERMISSIONS[role]),
    )
    if session == "inactive":
        user = replace(user, account_status="pending_broker_activation")
    if session == "permission_removed":
        user = replace(user, permissions=frozenset())
    if session != "missing":
        app.dependency_overrides[get_current_user] = lambda: user
    method, path, permission, body = ROUTES[index]
    allowed = session != "missing" and (
        permission == "authenticated"
        or (
            user.account_status == "active"
            and (
                permission in user.permissions
                or (permission == "trader" and role in {"investor", "broker"})
                or permission == role
            )
        )
    )
    client = TestClient(app)
    response = client.request(
        method,
        "/api/v1" + path,
        params={**PERIOD, "symbol": "AAPL", "side": "buy", "qty": "1", "price": "10"},
        json=body,
    )
    expected = 401 if session == "missing" else 418 if allowed else 403
    assert response.status_code == expected, response.text
    assert spy.calls == int(allowed)
    # Invalid params must not weaken access checks or reach a service.
    if not allowed:
        response = client.request(
            method,
            "/api/v1" + path,
            params={"from": "bad", "page_size": 0},
            json={"totp_code": "sensitive", "unexpected": "field"},
        )
        assert response.status_code == expected
        assert spy.calls == 0
        assert "sensitive" not in response.text


@pytest.mark.parametrize("role", ["auditor", "analyst"])
def test_read_roles_cannot_create_privileged_assignments(api_settings, role):
    # Even an erroneous broad permission grant cannot bypass the role check.
    app = create_app(api_settings)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        UUID(int=10),
        UUID(int=20),
        "user@test",
        "active",
        False,
        frozenset({role}),
        frozenset({"admin:rbac", "admin:fees", "admin:compliance", "admin:halts"}),
    )
    client = TestClient(app)
    for assignment in ("administrator", "auditor", "analyst", "broker"):
        response = client.post(
            f"/api/v1/admin/users/{IDENT}/roles",
            json={"role": assignment, "valid_from": "2026-11-20T00:00:00Z"},
        )
        assert response.status_code == 403
    assert (
        client.post("/api/v1/admin/trading-halts", json={**DECISION, "scope": "global"}).status_code
        == 403
    )


def test_openapi_preserves_existing_schemas_and_exposes_new_contracts(api_settings):
    document = create_app(api_settings).openapi()
    assert "ExecutionOut" in document["components"]["schemas"]
    schema = document["components"]["schemas"]["CommissionQuoteOut"]
    assert schema["properties"]["commission_rate_pct"]["type"] == "string"
    paths = document["paths"]
    assert "Schema owners" in paths["/api/v1/admin/audit-trail"]["get"]["description"]
    for path, methods in paths.items():
        if path.startswith("/api/v1/admin/") and any(
            part in path
            for part in ("fee-schedules", "trading-halts", "compliance", "audit-trail", "kpis")
        ):
            for operation in methods.values():
                assert {"401", "403", "422", "503"} <= operation["responses"].keys()


def test_denials_log_request_metadata_without_body_or_totp(api_settings, caplog):
    import logging

    app = create_app(api_settings)
    client = TestClient(app)
    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/api/v1/admin/trading-halts",
            json={
                "scope": "global",
                "reason": "private-body-text",
                "totp_code": "private-totp-code",
            },
        )
    assert response.status_code == 401
    records = [r for r in caplog.records if "Admin access rejected" in r.getMessage()]
    assert len(records) == 1
    record = records[0]
    assert record.request_id == response.headers["x-request-id"]
    assert "POST" in record.getMessage() and "NOT_AUTHENTICATED" in record.getMessage()
    assert "private-body-text" not in record.getMessage()
    assert "private-totp-code" not in record.getMessage()
