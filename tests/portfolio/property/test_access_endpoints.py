from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.portfolio.domain.model import Period, Report
from tests.portfolio.api.support import api_for


# Feature: portfolio-mod-05, Property 11: Control de acceso de los endpoints
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    st.sampled_from(["absent", "invalid", "valid"]),
    st.sampled_from(
        [
            frozenset(),
            frozenset({"investor"}),
            frozenset({"broker"}),
            frozenset({"investor", "broker"}),
        ]
    ),
    st.booleans(),
    st.booleans(),
    st.booleans(),
)
def test_endpoint_decision_model(api_settings, auth, roles, account, owns, linked):
    app, source, alpaca, repo = api_for(api_settings)
    uid, client_id, other = source.account.user_id, uuid4(), uuid4()
    now = app.state.portfolio_service.clock.now()
    period = Period(date(2026, 1, 1), date(2026, 1, 31))
    own_report, broker_report, client_report = uuid4(), uuid4(), uuid4()
    for ident, owner, role, type in [
        (own_report, uid, "investor", "on_demand"),
        (broker_report, uid, "broker", "broker"),
        (client_report, client_id, "investor", "on_demand"),
    ]:
        repo.values[ident] = Report(
            ident, owner if owns else other, role, type, period, now, {}, now
        )
    if not account:
        source.account = None
    if linked:
        source.links.add((uid, client_id))
    user = CurrentUser(uid, uuid4(), "test@example.com", "active", False, roles)
    if auth == "valid":
        app.dependency_overrides[get_current_user] = lambda: user
    endpoints = [
        ("GET", "/positions", "investor", False, False, True),
        ("GET", "/executions", "investor", False, False, False),
        ("GET", "/statistics", "investor", False, False, False),
        ("GET", "/risk-profile", "investor", False, False, True),
        ("POST", "/reports", "investor", False, False, True),
        ("GET", "/reports", "investor", False, False, True),
        ("GET", f"/reports/{own_report}", "investor", False, True, True),
        ("POST", "/broker/reports", "broker", False, False, linked),
        ("GET", "/broker/reports", "broker", False, False, False),
        ("GET", f"/broker/reports/{broker_report}", "broker", False, True, False),
        ("GET", f"/broker/clients/{client_id}/positions", "broker", True, False, True),
        (
            "GET",
            f"/broker/clients/{client_id}/reports/{client_report}",
            "broker",
            True,
            True,
            False,
        ),
    ]
    params = {"from": "2026-01-01", "to": "2026-01-31"}
    with TestClient(app) as client:
        if auth == "invalid":
            client.cookies.set("access_token", "invalid-token")
        for method, path, required, client_resource, report_resource, needs_account in endpoints:
            alpaca.calls = 0
            if auth != "valid":
                status, code = 401, "NOT_AUTHENTICATED"
            elif required not in roles:
                status, code = 403, "FORBIDDEN"
            elif (client_resource and not linked) or (report_resource and not owns):
                status, code = 404, "NOT_FOUND"
            elif needs_account and not account:
                status, code = 409, "ACCOUNT_NOT_LINKED"
            else:
                status, code = (201 if method == "POST" else 200), None
            response = client.request(
                method,
                "/api/v1/portfolio" + path,
                **({"json": params} if method == "POST" else {"params": params}),
            )
            assert response.status_code == status, (path, response.text)
            if code:
                assert response.json()["code"] == code
            if status in {401, 403, 404}:
                assert alpaca.calls == 0
