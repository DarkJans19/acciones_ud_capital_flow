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
