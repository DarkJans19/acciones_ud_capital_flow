from uuid import uuid4

import httpx

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.wallet.adapters.outbound.stripe.fake_stripe import FakeStripe
from acciones_ud.wallet.application.stripe_webhook_service import StripeWebhookService
from acciones_ud.wallet.domain.model import Subscription
from tests.wallet.property.test_webhooks import event, signed
from tests.wallet.support import funding_setup


async def test_deposit_withdrawal_and_signed_webhook(api_settings) -> None:
    service, uow, alpaca, user_id, bank, clock = await funding_setup()
    app = create_app(api_settings)
    app.state.funding_service = service
    app.state.wallet_clock = clock
    app.state.stripe_webhook_service = StripeWebhookService(uow, "whsec_test", FakeStripe())
    user = CurrentUser(
        user_id, uuid4(), "investor@example.com", "active", False, frozenset({"investor"})
    )
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        body = {"bank_relationship_id": str(bank.id), "amount": "12.34", "currency": "USD"}
        headers = {"Idempotency-Key": "deposit123"}
        result = await client.post("/api/v1/wallet/deposits", json=body, headers=headers)
        assert result.status_code == 201, result.text
        assert result.json()["amount"] == "12.34"
        assert "Virtual funds" in result.json()["sandbox_notice"]
        repeat = await client.post("/api/v1/wallet/deposits", json=body, headers=headers)
        assert repeat.json()["id"] == result.json()["id"] and alpaca.creations == 1
        body["amount"] = "5000.00"
        result = await client.post(
            "/api/v1/wallet/withdrawals", json=body, headers={"Idempotency-Key": "withdraw123"}
        )
        assert result.status_code == 422 and result.json()["code"] == "INSUFFICIENT_FUNDS"
        await uow.work.subscriptions.insert(
            Subscription(
                uuid4(), user_id, "monthly", "pending_checkout", "cs_test", "sub_test", "cus_test"
            )
        )
        message = event("evt_api", "active", int(clock.now().timestamp()))
        payload, signature = signed(message, clock)
        app.dependency_overrides.clear()
        result = await client.post(
            "/api/v1/webhooks/stripe", content=payload, headers={"Stripe-Signature": signature}
        )
        assert result.status_code == 200 and uow.work.premium.values[user_id]
    if app.state.wallet_stripe_http is not None:
        await app.state.wallet_stripe_http.aclose()


async def test_every_wallet_endpoint_requires_session_and_investor(api_settings) -> None:
    app = create_app(api_settings)
    operations = [
        (path.replace("{id}", str(uuid4())), method)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith(("/api/v1/wallet", "/api/v1/subscriptions"))
        for method in methods
    ]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        for expected in (401, 403):
            if expected == 403:
                user = CurrentUser(
                    uuid4(), uuid4(), "broker@example.com", "active", False, frozenset({"broker"})
                )
                app.dependency_overrides[get_current_user] = lambda user=user: user
            for path, method in operations:
                response = await client.request(method, path)
                assert response.status_code == expected, (path, response.text)
    if app.state.wallet_stripe_http is not None:
        await app.state.wallet_stripe_http.aclose()


def test_checkout_payment_unlocks_a_premium_watchlist(api_settings) -> None:
    from acciones_ud.wallet.application.subscription_service import SubscriptionService
    from tests.market_data.test_watchlists_alerts_api import build
    from tests.support.clock import FakeClock
    from tests.wallet.fakes import MemoryFactory

    user_id = uuid4()
    client, *_ = build(api_settings, premium=False, user_id=user_id)
    app = client.app
    uow, stripe, clock = MemoryFactory(), FakeStripe(), FakeClock()
    app.state.subscription_service = SubscriptionService(
        uow, stripe, clock, "price_monthly", "price_annual"
    )
    app.state.stripe_webhook_service = StripeWebhookService(uow, "whsec_test", stripe)
    app.state.wallet_clock = clock
    session_id = uuid4()

    def current():
        return CurrentUser(
            user_id,
            session_id,
            "investor@example.com",
            "active",
            uow.work.premium.values.get(user_id, False),
            frozenset({"investor"}),
            frozenset({"market:read", "watchlist:manage"}),
        )

    app.dependency_overrides[get_current_user] = current
    denied = client.post("/api/v1/watchlists", json={"name": "Paid feature"})
    assert denied.status_code == 403 and denied.json()["code"] == "PREMIUM_REQUIRED"
    checkout = client.post("/api/v1/subscriptions/checkout", json={"plan": "monthly"})
    assert checkout.status_code == 201, checkout.text
    assert stripe.checkouts == 1 and not uow.work.premium.values
    stripe.subscriptions["sub_paid"] = {
        "id": "sub_paid",
        "customer": "cus_paid",
        "status": "active",
        "current_period_start": int(clock.now().timestamp()),
        "current_period_end": int(clock.now().timestamp()) + 2592000,
    }
    message = {
        "id": "evt_paid_checkout",
        "type": "checkout.session.completed",
        "created": int(clock.now().timestamp()),
        "data": {
            "object": {"id": checkout.json()["checkout_session_id"], "subscription": "sub_paid"}
        },
    }
    payload, signature = signed(message, clock)
    for _ in range(2):
        result = client.post(
            "/api/v1/webhooks/stripe", content=payload, headers={"Stripe-Signature": signature}
        )
        assert result.status_code == 200
    invoice = {
        "id": "evt_paid_invoice",
        "type": "invoice.paid",
        "created": int(clock.now().timestamp()),
        "data": {
            "object": {
                "id": "in_paid",
                "subscription": "sub_paid",
                "amount_paid": 1200,
                "currency": "usd",
            }
        },
    }
    invoice_payload, invoice_signature = signed(invoice, clock)
    for _ in range(2):
        paid = client.post(
            "/api/v1/webhooks/stripe",
            content=invoice_payload,
            headers={"Stripe-Signature": invoice_signature},
        )
        assert paid.status_code == 200
    payments = client.get("/api/v1/subscriptions/me/payments")
    assert payments.status_code == 200 and len(payments.json()["items"]) == 1
    payment = payments.json()["items"][0]
    assert payment["amount"] == "12" and payment["result"] == "paid"
    assert client.get(f"/api/v1/subscriptions/me/payments/{payment['id']}").status_code == 200
    assert client.get("/api/v1/subscriptions/plans").status_code == 200
    assert uow.work.premium.values[user_id] is True
    assert len(uow.work.events.values) == 2
    assert client.get("/api/v1/subscriptions/me").json()["subscription"]["status"] == "active"
    created = client.post("/api/v1/watchlists", json={"name": "Paid feature"})
    assert created.status_code == 201, created.text
    watchlist = created.json()["id"]
    added = client.post(f"/api/v1/watchlists/{watchlist}/items", json={"symbol": "AAPL"})
    assert added.status_code == 200 and added.json()["symbols"] == ["AAPL"]
    duplicate_checkout = client.post("/api/v1/subscriptions/checkout", json={"plan": "monthly"})
    assert duplicate_checkout.status_code == 409 and stripe.checkouts == 1

    canceled = client.post("/api/v1/subscriptions/me/cancel", json={"reason": "At period end"})
    assert canceled.status_code == 200 and canceled.json()["cancel_at_period_end"] is True
    assert uow.work.premium.values[user_id] is True
