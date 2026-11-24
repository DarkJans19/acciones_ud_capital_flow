"""RF-01/02/24/26/30/41/44: seven modules, real cookies and PostgreSQL.

Only external providers are doubled. All HTTP dependencies, RBAC, domain,
application services, SQL repositories, hashing, encryption and JWTs are real.
The session's migrated_database fixture destroys this disposable schema.
"""

import hashlib
import hmac
import json
import os
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import pyotp
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from acciones_ud.identity.adapters.outbound.persistence.user_repository import UserRepository
from acciones_ud.identity.adapters.outbound.security.passwords import PasswordHasher
from acciones_ud.identity.domain.registration import build_new_user
from acciones_ud.main import create_app
from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import (
    FakeAlpacaBrokerMarket,
    calendar_session,
    instrument,
)
from acciones_ud.market_data.adapters.outbound.alpaca.fake_data import FakeAlpacaData
from acciones_ud.market_data.adapters.outbound.persistence.instrument_repository import (
    InstrumentRepository,
)
from acciones_ud.market_data.domain.entities import Snapshot
from acciones_ud.wallet.adapters.outbound.stripe.fake_stripe import FakeStripe
from acciones_ud.wallet.application.stripe_webhook_service import StripeWebhookService
from acciones_ud.wallet.application.subscription_service import SubscriptionService
from acciones_ud.wallet.composition import wallet_uow
from tests.identity.test_financial_profile import kyc_payload
from tests.identity.test_registration_security import payload

pytestmark = pytest.mark.db


async def test_seven_module_journey_and_cross_tenant_denials(
    migrated_database, api_settings, monkeypatch
):
    from acciones_ud.shared.infrastructure import db

    assert "localhost:55432" in migrated_database or "127.0.0.1:55432" in migrated_database
    engine = db.build_engine(migrated_database)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db, "session_factory", factory)
    app = create_app(api_settings)
    rows, upstream_calls = [], []
    tag = "audit-" + uuid4().hex
    symbol = "T" + uuid4().hex[:7].upper()
    now = datetime.now(UTC)
    market = FakeAlpacaBrokerMarket()
    market.assets = [instrument(symbol, fractionable=True)]
    market.asset = market.assets[0]
    market.sessions = [
        calendar_session((now.date() + timedelta(days=n)).isoformat()) for n in range(32)
        if (now.date() + timedelta(days=n)).weekday() < 5
    ]
    data = FakeAlpacaData()
    data.snapshot_value = Snapshot(last_trade_price=Decimal("100"), quote_updated_at=now)
    data.snapshots_value = {symbol: data.snapshot_value}
    app.state.alpaca_broker_market = market
    app.state.alpaca_data_port = data
    banks, submissions = {}, {}

    def provider(request):
        path = request.url.path
        upstream_calls.append((request.method, path))
        body = json.loads(request.content) if request.content else {}
        if path == "/v1/accounts" and request.method == "POST":
            return httpx.Response(200, json={"id": str(uuid4()), "status": "ACTIVE"})
        if path.endswith("/account"):
            return httpx.Response(200, json={
                "status": "ACTIVE", "currency": "USD", "cash": "10000",
                "cash_withdrawable": "10000", "buying_power": "10000",
                "equity": "10000", "portfolio_value": "10000", "long_market_value": "0",
            })
        if path.endswith("/ach_relationships"):
            if request.method == "POST":
                bank = {"id": str(uuid4()), "status": "APPROVED", "created_at": now.isoformat()}
                banks[bank["id"]] = bank
                return httpx.Response(200, json=bank)
            return httpx.Response(200, json=list(banks.values()))
        if path.endswith("/transfers") and request.method == "POST":
            return httpx.Response(200, json={
                **body, "id": str(uuid4()), "status": "QUEUED",
                "created_at": now.isoformat(), "currency": "USD",
            })
        if path.endswith("/positions") or path == "/v1/accounts/activities":
            return httpx.Response(200, json=[])
        if path.endswith("/orders") and request.method == "POST":
            order = {
                **body, "id": str(uuid4()), "status": "new", "filled_qty": "0",
                "created_at": now.isoformat(), "updated_at": now.isoformat(),
            }
            submissions[order["id"]] = order
            return httpx.Response(200, json=order)
        if "/orders/" in path:
            ident = path.rsplit("/", 1)[-1]
            if request.method == "DELETE":
                return httpx.Response(204)
            if ident in submissions:
                return httpx.Response(200, json=submissions[ident])
        if path.startswith("/v1/accounts/") and request.method == "GET":
            return httpx.Response(200, json={"id": path.rsplit("/", 1)[-1], "status": "ACTIVE"})
        raise AssertionError(f"Unscripted outbound request: {request.method} {path}")

    async with AsyncExitStack() as stack:
        try:
            broker_http = await stack.enter_async_context(httpx.AsyncClient(
                base_url="https://provider.test", transport=httpx.MockTransport(provider)
            ))
            app.state.alpaca_broker = broker_http
            clients = {
                role: await stack.enter_async_context(httpx.AsyncClient(
                    base_url="https://api.test",
                    transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                ))
                for role in (
                    "admin", "investor", "other", "broker", "auditor", "analyst", "anonymous"
                )
            }

            async def call(actor, method, path, expected, **kwargs):
                response = await clients[actor].request(method, "/api/v1" + path, **kwargs)
                rows.append({
                    "actor": actor, "method": method, "path": path,
                    "expected": expected, "actual": response.status_code,
                    "passed": response.status_code == expected,
                    "code": response.json().get("code")
                    if response.status_code >= 400 else None,
                })
                assert response.status_code == expected, (actor, method, path, response.text)
                return response.json() if response.content else None

            admin_email = tag + "-admin@example.com"
            record, _ = build_new_user("administrator", {**payload(), "email": admin_email})
            record.update(
                password_hash=PasswordHasher().hash("SafePassword123"), terms_accepted_at=now
            )
            async with factory() as session, session.begin():
                await UserRepository(session).insert(record, "administrator")
                await InstrumentRepository(session).upsert_catalog(market.assets, now)

            users = {}
            for actor in ("admin", "investor", "other", "broker", "auditor", "analyst"):
                email = tag + "-" + actor + "@example.com"
                if actor != "admin":
                    body = {**payload(), "email": email}
                    if actor == "broker":
                        body.update(firm_name="Audit Firm", license_number="AUDIT123")
                    await call(
                        actor, "POST", "/auth/register/broker" if actor == "broker"
                        else "/auth/register", 201, json=body,
                    )
                challenge = await call(
                    actor, "POST", "/auth/login", 200,
                    json={"email": email, "password": "SafePassword123"},
                )
                secret = challenge["totp_enrollment"]["secret"]
                enrolled = await call(
                    actor, "POST", "/auth/mfa/verify", 200,
                    json={"mfa_token": challenge["mfa_token"], "code": pyotp.TOTP(secret).now()},
                )
                users[actor] = enrolled["user"]["user_id"]

            for actor in ("auditor", "analyst"):
                await call("admin", "POST", f"/admin/users/{users[actor]}/roles", 201, json={
                    "role": actor, "valid_from": (now - timedelta(minutes=1)).isoformat(),
                })
            await call("broker", "GET", "/wallet/balances", 403)
            await call("admin", "POST", f"/admin/users/{users['broker']}/broker-activation", 200)
            await call("investor", "GET", "/admin/fee-schedules", 403)
            # Registration also grants investor; after activation this dual-role
            # actor is authorized but still lacks its own linked KYC account.
            await call("broker", "GET", "/wallet/balances", 409)
            await call("investor", "POST", "/kyc/account", 201, json=kyc_payload())
            await call("investor", "GET", "/kyc/status", 200)
            await call("investor", "GET", "/wallet/balances", 200)
            await call("investor", "GET", "/watchlists", 403)

            # Real Stripe webhook signature + real wallet repositories. Only Stripe I/O is fake.
            stripe = FakeStripe()
            app.state.subscription_service = SubscriptionService(
                wallet_uow, stripe, app.state.wallet_clock, "price_monthly", "price_annual"
            )
            app.state.stripe_webhook_service = StripeWebhookService(
                wallet_uow, "whsec_audit", stripe
            )
            checkout = await call(
                "investor", "POST", "/subscriptions/checkout", 201, json={"plan": "monthly"}
            )
            stripe.subscriptions["sub_" + tag] = {
                "id": "sub_" + tag, "customer": "cus_" + tag, "status": "active",
                "current_period_start": int(now.timestamp()),
                "current_period_end": int((now + timedelta(days=30)).timestamp()),
            }
            event = json.dumps({
                "id": "evt_" + tag, "type": "checkout.session.completed",
                "created": int(now.timestamp()), "data": {"object": {
                    "id": checkout["checkout_session_id"], "subscription": "sub_" + tag,
                }},
            }).encode()
            stamp = str(int(now.timestamp()))
            signature = hmac.new(
                b"whsec_audit", stamp.encode() + b"." + event, hashlib.sha256
            ).hexdigest()
            await call("anonymous", "POST", "/webhooks/stripe", 400, content=event)
            for _ in range(2):
                await call(
                    "anonymous", "POST", "/webhooks/stripe", 200, content=event,
                    headers={"Stripe-Signature": f"t={stamp},v1={signature}"},
                )
            me = await call("investor", "GET", "/users/me", 200)
            assert me["is_premium"]
            await call("investor", "GET", "/instruments/search", 200, params={"q": symbol})
            await call("investor", "GET", f"/instruments/{symbol}/quote", 200)
            watchlist = await call(
                "investor", "POST", "/watchlists", 201, json={"name": "Audit watchlist"}
            )
            wid = watchlist["id"]
            await call("investor", "POST", f"/watchlists/{wid}/items", 200, json={"symbol": symbol})
            await call("investor", "POST", f"/watchlists/{wid}/items", 409, json={"symbol": symbol})

            bank = await call("investor", "POST", "/wallet/bank-relationships", 201, json={
                "account_owner_name": "Audit Investor", "bank_account_type": "CHECKING",
                "bank_account_number": "123456789", "bank_routing_number": "021000021",
            })
            await call("other", "GET", "/wallet/bank-relationships/" + bank["id"], 404)
            transfer_body = {"bank_relationship_id": bank["id"], "amount": "12.34"}
            headers = {"Idempotency-Key": tag + "-deposit"}
            transfer = await call(
                "investor", "POST", "/wallet/deposits", 201, json=transfer_body, headers=headers
            )
            repeat = await call(
                "investor", "POST", "/wallet/deposits", 201, json=transfer_body, headers=headers
            )
            assert transfer["id"] == repeat["id"]
            await call(
                "investor", "POST", "/wallet/deposits", 409,
                json={**transfer_body, "amount": "12.35"}, headers=headers,
            )
            await call("other", "GET", "/wallet/transfers/" + transfer["id"], 404)

            await call("admin", "GET", "/admin/fee-schedules", 200)
            quote = await call(
                "investor", "GET", "/commissions/quote", 200,
                params={"symbol": symbol, "side": "buy", "qty": "1", "price": "100"},
            )
            assert Decimal(quote["commission"]) == 2
            body = {"symbol": symbol, "side": "buy", "qty": "1", "type": "market",
                    "confirmed": True, "schedule_if_closed": True}
            await call("investor", "POST", "/orders/preview", 200, json=body)
            headers = {"Idempotency-Key": tag + "-order"}
            order = await call("investor", "POST", "/orders", 201, json=body, headers=headers)
            repeated = await call("investor", "POST", "/orders", 201, json=body, headers=headers)
            assert order["id"] == repeated["id"] and order["fee_version_id"]
            await call("other", "GET", "/orders/" + order["id"], 404)
            await call("investor", "GET", "/portfolio/positions", 200)
            period = {"from": now.date().isoformat(), "to": now.date().isoformat()}
            report = await call("investor", "POST", "/portfolio/reports", 201, json=period)
            await call("other", "GET", "/portfolio/reports/" + report["id"], 404)

            link = await call("investor", "POST", "/broker-links", 201, json={
                "broker_id": users["broker"], "consent_accepted": True,
            })
            lid = link["id"]
            await call("other", "POST", f"/broker-links/{lid}/end", 404,
                       json={"reason": "Foreign actor", "confirmed": True})
            await call("broker", "POST", f"/broker/link-requests/{lid}/accept", 200)
            proposal = await call("broker", "POST", "/broker/proposals", 201, json={
                "investor_id": users["investor"], "symbol": symbol,
                "side": "buy", "qty": "1", "type": "market",
            })
            await call("other", "GET", "/proposals/" + proposal["id"], 404)
            await call("investor", "POST", "/proposals/" + proposal["id"] + "/decision", 200,
                       json={"version": 1, "decision": "reject", "comment": "Audit rejection"})
            await call("investor", "POST", f"/broker-links/{lid}/end", 200,
                       json={"reason": "Audit complete", "confirmed": True})
            await call("broker", "GET", "/broker/clients/" + users["investor"] + "/orders", 404)
            await call("admin", "GET", "/admin/audit-trail", 200, params=period)
            await call("auditor", "GET", "/admin/audit-trail", 200, params=period)
            await call("analyst", "GET", "/admin/kpis", 200, params=period)
            await call("analyst", "GET", "/admin/audit-trail", 403, params=period)
            await call("auditor", "GET", "/admin/kpis", 403, params=period)
            for actor in ("auditor", "analyst"):
                await call(actor, "POST", "/admin/trading-halts", 403,
                           json={"scope": "global", "reason": "Must not mutate"})
            for actor in ("investor", "other", "broker", "admin", "auditor", "analyst"):
                await call(actor, "POST", "/auth/logout", 204)
                await call(actor, "GET", "/users/me", 401)
        finally:
            output = os.environ.get("AUDIT_JOURNEY_EVIDENCE")
            if output:
                Path(output).write_text(json.dumps({
                    "mode": "ASGI + real PostgreSQL; fake Alpaca/Stripe; real authentication",
                    "requests": rows, "provider_request_count": len(upstream_calls),
                }, indent=2) + "\n")
            if app.state.wallet_stripe_http:
                await app.state.wallet_stripe_http.aclose()
            await engine.dispose()
