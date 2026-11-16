from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.domain import entities as e
from tests.brokers.api.support import app_for
from tests.brokers.support import context

INV, BROKER, OTHER, LINK, PROPOSAL = [UUID(int=i) for i in range(1, 6)]
ROUTES = [
    ("GET", "/brokers/suggestions", None, "investor", "list"),
    ("GET", "/brokers?q=Firm", None, "investor", "list"),
    (
        "PUT",
        "/brokers/me/profile",
        {"specialty": "Stocks", "years_experience": 1},
        "broker",
        "profile",
    ),
    ("GET", "/brokers/{broker}", None, "public", "public"),
    ("GET", "/brokers/{broker}/reputation", None, "authenticated", "public"),
    ("GET", "/brokers/{broker}/reviews", None, "authenticated", "public"),
    ("PUT", "/brokers/{broker}/rating", {"stars": 5}, "investor", "rating"),
    (
        "POST",
        "/broker-links",
        {"broker_id": str(BROKER), "consent_accepted": True},
        "investor",
        "list",
    ),
    ("GET", "/broker-links/current", None, "investor", "list"),
    ("GET", "/broker-links", None, "investor", "list"),
    ("POST", "/broker-links/{link}/cancel", {}, "investor", "link"),
    (
        "POST",
        "/broker-links/{link}/end",
        {"reason": "Ended", "confirmed": True},
        "investor",
        "link",
    ),
    ("PUT", "/broker-links/{link}/order-review", {"enabled": True}, "investor", "link"),
    (
        "POST",
        "/broker-links/{link}/trading-authorization",
        {"consent_accepted": True},
        "investor",
        "link",
    ),
    ("POST", "/broker-links/{link}/trading-authorization/revoke", {}, "investor", "link"),
    ("GET", "/broker/link-requests", None, "broker", "list"),
    ("POST", "/broker/link-requests/{link}/accept", {}, "broker", "link"),
    ("POST", "/broker/link-requests/{link}/decline", {"reason": "Declined"}, "broker", "link"),
    (
        "POST",
        "/broker/proposals",
        {"investor_id": str(INV), "symbol": "AAPL", "side": "buy", "qty": "1", "type": "market"},
        "broker",
        "create",
    ),
    ("GET", "/broker/proposals", None, "broker", "list"),
    ("GET", "/broker/proposals/{proposal}", None, "broker", "proposal"),
    (
        "PUT",
        "/broker/proposals/{proposal}",
        {"version": 1, "symbol": "AAPL", "side": "buy", "qty": "1", "type": "market"},
        "broker",
        "proposal",
    ),
    (
        "POST",
        "/broker/proposals/{proposal}/withdraw",
        {"version": 1, "reason": "Withdrawn", "confirmed": True},
        "broker",
        "proposal",
    ),
    (
        "POST",
        "/broker/proposals/{proposal}/decision",
        {"version": 1, "decision": "approve"},
        "broker",
        "proposal",
    ),
    ("POST", "/broker/proposals/{proposal}/messages", {"body": "Evidence"}, "broker", "proposal"),
    ("GET", "/broker/proposals/{proposal}/messages", None, "broker", "proposal"),
    ("GET", "/proposals", None, "investor", "list"),
    ("GET", "/proposals/{proposal}", None, "investor", "proposal"),
    (
        "POST",
        "/proposals/{proposal}/decision",
        {"version": 1, "decision": "accept"},
        "investor",
        "proposal",
    ),
    ("POST", "/proposals/{proposal}/messages", {"body": "Evidence"}, "investor", "message"),
    ("GET", "/proposals/{proposal}/messages", None, "investor", "proposal"),
    ("GET", "/broker/clients", None, "broker", "list"),
    ("GET", "/broker/clients/{investor}/orders", None, "broker", "client"),
]


def scenario(link_state, roles, owned, role):
    ctx = context()
    ctx.directory.add(INV, "investor")
    ctx.directory.add(BROKER, "broker")
    ctx.directory.add(OTHER, "investor")
    ctx.directory.add(OTHER, "broker")
    actor = (BROKER if role == "broker" else INV) if owned else OTHER
    ctx.directory.roles[actor] = set(roles)
    if link_state == "revoked":
        ctx.directory.roles[BROKER].discard("broker")
    now = ctx.clock.now()
    if link_state != "missing":
        state = e.LinkStatus.ACTIVE if link_state == "revoked" else e.LinkStatus(link_state)
        link = e.Link(
            LINK,
            INV,
            BROKER,
            state,
            now,
            now + timedelta(days=7),
            "v1",
            now,
            started_at=now if state == e.LinkStatus.ACTIVE else None,
        )
        ctx.uow.work.links.values[(LINK,)] = link
        if state == e.LinkStatus.ACTIVE:
            auth = e.TradingAuthorization(UUID(int=10), LINK, "v1", now)
            ctx.uow.work.authorizations.values[(auth.id,)] = auth
    ctx.accounts.linked.add(INV)
    proposal = e.Proposal(
        PROPOSAL,
        LINK,
        BROKER,
        INV,
        e.ProposalStatus.ACCEPTED,
        1,
        now,
        now,
        now,
        now + timedelta(hours=72),
        accepted_version=1,
    )
    ctx.uow.work.proposals.values[(PROPOSAL,)] = proposal
    version = e.ProposalVersion(
        PROPOSAL, 1, "AAPL", "buy", Decimal(1), "market", None, Decimal(100), Decimal(102), now
    )
    ctx.uow.work.versions.values[(PROPOSAL, 1)] = version
    return ctx, actor


# Feature: brokers-mod-06, Property 6: Control de acceso de los endpoints
@settings(max_examples=100)
@given(
    st.sampled_from(["absent", "invalid", "valid"]),
    st.sampled_from([(), ("investor",), ("broker",), ("investor", "broker")]),
    st.booleans(),
    st.sampled_from(["missing", "requested", "active", "ended", "revoked"]),
)
def test_every_endpoint_enforces_auth_role_ownership_before_order_ports(
    auth, roles, owned, link_state
):
    app = app_for(context())
    client = TestClient(app)
    for method, path, body, role, kind in ROUTES:
        ctx, actor = scenario(link_state, roles, owned, role)
        app.state.brokers_context = ctx
        client.cookies.clear()
        if auth != "absent":
            client.cookies.set("access_token", str(actor) if auth == "valid" else "invalid")
        expected = None
        if role != "public" and auth != "valid":
            expected = 401, "NOT_AUTHENTICATED"
        elif role in {"broker", "investor"} and role not in ctx.directory.roles[actor]:
            expected = 403, "FORBIDDEN"
        elif (
            kind == "public" or (method == "POST" and path == "/broker-links")
        ) and "broker" not in ctx.directory.roles[BROKER]:
            expected = 404, "BROKER_NOT_FOUND"
        elif kind == "link" and (not owned or link_state == "missing"):
            expected = 404, "LINK_NOT_FOUND"
        elif kind in {"proposal", "message", "client", "create"}:
            needs_active = role == "broker" or kind == "message"
            active = link_state == "active" and "broker" in ctx.directory.roles[BROKER]
            if not owned or (needs_active and not active):
                code = "CLIENT_NOT_FOUND" if kind in {"client", "create"} else "PROPOSAL_NOT_FOUND"
                expected = 404, code
        url = "/api/v1" + path.format(broker=BROKER, investor=INV, link=LINK, proposal=PROPOSAL)
        response = client.request(method, url, json=body)
        if expected:
            assert (response.status_code, response.json()["code"]) == expected, (
                method,
                path,
                response.text,
            )
            assert response.json()["details"] is None
            assert str(INV) not in response.text and str(BROKER) not in response.text
            assert not ctx.order_creation.creation_calls and not ctx.order_query.query_calls
        else:
            assert response.status_code in {200, 201, 409, 422}, (method, path, response.text)
        assert "alpaca_account_id" not in response.text and "totp_code" not in response.text
