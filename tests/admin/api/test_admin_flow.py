from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from acciones_ud.admin.application.commission_service import (
    CommissionQueryService,
    CommissionQuoteService,
)
from acciones_ud.admin.application.compliance_service import ComplianceService
from acciones_ud.admin.application.fee_service import FeeService
from acciones_ud.admin.application.halt_service import HaltService
from acciones_ud.admin.application.kpi_service import KpiService
from acciones_ud.admin.application.market_admin_view import MarketAdminView
from acciones_ud.admin.application.restriction_service import RestrictionService
from acciones_ud.admin.domain.atypical import AtypicalConfig
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from tests.admin.api.test_access_control import PERMISSIONS
from tests.admin.fakes import Ledger, Markets, Users, setup
from tests.admin.property.test_rules import execution
from tests.admin.unit.test_behavior_and_cache import Source, Trail


def test_admin_flow_decimal_contract_fixed_fees_halts_compliance_and_kpis(api_settings):
    uow, clock, actor, step = setup()
    clock.advance(12 * 3600)
    user = uuid4()
    app = create_app(api_settings)
    principal = CurrentUser(
        actor,
        uuid4(),
        "admin@test",
        "active",
        False,
        frozenset({"administrator"}),
        frozenset(PERMISSIONS["administrator"]),
    )
    app.dependency_overrides[get_current_user] = lambda: principal

    class Catalog(Markets):
        async def markets(self):
            return [
                {
                    "code": "NASDAQ",
                    "name": "Nasdaq",
                    "timezone": "America/New_York",
                    "default_schedule": None,
                    "overrides": [],
                }
            ]

    class Links:
        async def linked_investors(self, broker):
            return [user]

        async def is_linked(self, broker, investor):
            return investor == user

    markets, users = Catalog(), Users()
    ledger = Ledger([replace(execution(1, 100, user=user), executed_at=clock.now())])
    app.state.admin_fees = FeeService(uow, markets, step, clock)
    app.state.admin_quote = CommissionQuoteService(uow, markets, clock)
    app.state.admin_commissions = CommissionQueryService(ledger, Links(), users)
    app.state.admin_halts = HaltService(uow, markets, step, clock)
    app.state.admin_restrictions = RestrictionService(uow, users, step, clock)
    app.state.admin_markets = MarketAdminView(uow, markets, clock)
    app.state.admin_compliance = ComplianceService(
        uow, ledger, Trail(), users, clock, AtypicalConfig()
    )
    app.state.admin_kpis = KpiService(uow, Source(), ledger, clock, 300)
    client = TestClient(app)
    decision = {"reason": "Approved by operations", "totp_code": "123456"}
    future = (clock.now() + timedelta(days=1)).isoformat()
    response = client.post(
        "/api/v1/admin/fee-schedules/NASDAQ/versions",
        json={
            **decision,
            "commission_rate_pct": "1.7500",
            "platform_share_pct": "60.00",
            "expected_latest_version": 0,
            "effective_from": future,
        },
    )
    assert response.status_code == 201, response.text
    version = response.json()
    assert version["commission_rate_pct"] == "1.75" and version["status"] == "scheduled"
    matrix = client.get("/api/v1/admin/fee-schedules")
    assert matrix.status_code == 200, matrix.text
    assert matrix.json()["items"][1]["terms"]["commission_rate_pct"] == "2"
    assert len(matrix.json()["items"][1]["scheduled"]) == 1
    history = client.get("/api/v1/admin/fee-schedules/NASDAQ/versions")
    assert history.status_code == 200 and history.json()["items"][0]["id"] == version["id"]
    cancel = client.post(
        f"/api/v1/admin/fee-schedules/NASDAQ/versions/{version['id']}/cancel", json=decision
    )
    assert cancel.status_code == 200 and cancel.json()["status"] == "canceled"
    response = client.post("/api/v1/admin/trading-halts", json={**decision, "scope": "global"})
    assert response.status_code == 201, response.text
    halt = response.json()
    public = client.get("/api/v1/trading-halts/active")
    assert set(public.json()[0]) == {"scope", "starts_at", "ends_at"}
    markets_response = client.get("/api/v1/admin/markets")
    assert markets_response.status_code == 200, markets_response.text
    assert markets_response.json()[0]["trading_halts"][0]["id"] == halt["id"]
    released = client.post(f"/api/v1/admin/trading-halts/{halt['id']}/release", json=decision)
    assert released.status_code == 200 and released.json()["status"] == "released"
    response = client.post(
        "/api/v1/admin/compliance/restrictions",
        json={
            **decision,
            "user_id": str(user),
            "evidence_text": "Review case",
            "evidence_refs": [],
        },
    )
    assert response.status_code == 201, response.text
    restriction = response.json()
    assert client.get("/api/v1/admin/compliance/restrictions").status_code == 200
    lifted = client.post(
        f"/api/v1/admin/compliance/restrictions/{restriction['id']}/lift", json=decision
    )
    assert lifted.status_code == 200 and lifted.json()["status"] == "lifted"
    period = {"from": clock.now().date().isoformat(), "to": clock.now().date().isoformat()}
    response = client.post(f"/api/v1/admin/compliance/users/{user}/audit-reports", json=period)
    assert response.status_code == 201, response.text
    report = response.json()
    assert client.get(f"/api/v1/admin/compliance/audit-reports/{report['id']}").json() == report
    commissions = client.get("/api/v1/admin/commissions", params=period)
    assert commissions.status_code == 200, commissions.text
    assert commissions.json()["items"][0]["commission"] == "2"
    dashboard = client.get("/api/v1/admin/kpis", params=period)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["metrics"]["platform_commissions_usd"]["value"] == "2"
    principal = replace(principal, roles=frozenset({"investor"}), permissions=frozenset())
    quote = client.get(
        "/api/v1/commissions/quote",
        params={
            "symbol": "AAPL",
            "side": "buy",
            "qty": "10",
            "price": "187.35",
            "with_broker": True,
        },
    )
    assert quote.status_code == 200, quote.text
    assert quote.json()["commission"] == "37.47" and not quote.json()["binding"]
    assert quote.json()["platform_share"] == "22.48"
    assert quote.json()["broker_share"] == "14.99"
    assert "123456" not in str([record.payload for record in uow.work.audit.rows])
