import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.shared.domain.errors import AppError
from acciones_ud.wallet.adapters.outbound.stripe.fake_stripe import FakeStripe
from acciones_ud.wallet.application.stripe_webhook_service import StripeWebhookService
from acciones_ud.wallet.application.subscription_service import SubscriptionService
from acciones_ud.wallet.domain.model import Payment, Subscription
from tests.support.clock import FakeClock
from tests.wallet.fakes import MemoryFactory


def signed(event, clock):
    payload = json.dumps(event).encode()
    stamp = int(clock.now().timestamp())
    signature = hmac.new(
        b"whsec_test", str(stamp).encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    return payload, f"t={stamp},v1={signature}"


async def setup_webhook():
    uow, clock, user_id = MemoryFactory(), FakeClock(), uuid4()
    await uow.work.subscriptions.insert(
        Subscription(
            uuid4(), user_id, "monthly", "pending_checkout", "cs_test", "sub_test", "cus_test"
        )
    )
    return uow, clock, user_id, StripeWebhookService(uow, "whsec_test", FakeStripe())


def event(ident, status, at):
    return {
        "id": ident,
        "type": "customer.subscription.updated",
        "created": at,
        "data": {"object": {"id": "sub_test", "customer": "cus_test", "status": status}},
    }


# Feature: wallet-mod-04, Property 8: Idempotencia de Stripe_Events
@settings(max_examples=100)
@given(st.lists(st.integers(0, 4), min_size=1, max_size=20))
async def test_webhook_idempotency(sequence) -> None:
    uow, clock, user, handler = await setup_webhook()
    baseline = []
    for ident in sequence:
        message = event(
            f"evt_{ident}", "active" if ident % 2 else "canceled", int(clock.now().timestamp())
        )
        await handler.handle(*signed(message, clock), clock.now())
        if ident not in baseline:
            baseline.append(ident)
    assert len(uow.work.events.values) == len(baseline)
    assert uow.work.premium.values[user] is bool(baseline[-1] % 2)


# Feature: wallet-mod-04, Property 9: Efecto de la suscripción sobre is_premium
@settings(max_examples=100)
@given(
    st.lists(
        st.sampled_from(
            ["active", "trialing", "canceled", "unpaid", "incomplete_expired", "past_due"]
        ),
        min_size=1,
        max_size=15,
    ),
    st.booleans(),
)
async def test_premium_sequence(statuses, initial) -> None:
    uow, clock, user, handler = await setup_webhook()
    uow.work.premium.values[user] = initial
    expected = initial
    for index, status in enumerate(statuses):
        message = event(f"evt_{index}", status, int(clock.now().timestamp()))
        await handler.handle(*signed(message, clock), clock.now())
        if status in {"active", "trialing"}:
            expected = True
        elif status in {"canceled", "unpaid", "incomplete_expired"}:
            expected = False
        assert uow.work.premium.values[user] is expected


# Feature: wallet-mod-04, Property 10: Eventos no asociados sin efectos
@settings(max_examples=100)
@given(st.uuids())
async def test_unassociated(ident) -> None:
    uow, clock, _, handler = await setup_webhook()
    before = list(uow.work.subscriptions.values)
    message = event(str(ident), "active", int(clock.now().timestamp()))
    message["data"]["object"] = {"id": "unknown", "customer": "unknown", "status": "active"}
    await handler.handle(*signed(message, clock), clock.now())
    assert uow.work.subscriptions.values == before and not uow.work.premium.values
    assert uow.work.events.values[0].outcome == "unassociated"


# Feature: wallet-mod-04, Property 7: Firma inválida sin efectos
@settings(max_examples=100)
@given(st.binary())
async def test_invalid_signature_no_effects(body) -> None:
    uow, clock, _, handler = await setup_webhook()
    before = list(uow.work.subscriptions.values)
    with pytest.raises(AppError) as caught:
        await handler.handle(body, "invalid", clock.now())
    assert caught.value.status == 400
    assert uow.work.subscriptions.values == before
    assert not uow.work.events.values and not uow.work.payments.values
    assert not uow.work.premium.values


# Feature: wallet-mod-04, Property 6: Recursos ajenos indistinguibles de inexistentes
@settings(max_examples=100)
@given(st.uuids())
async def test_payment_ownership(other) -> None:
    uow, clock, owner, _ = await setup_webhook()
    subscription = uow.work.subscriptions.values[0]
    payment = Payment(
        uuid4(),
        owner,
        subscription.id,
        "invoice",
        "monthly",
        12,
        "USD",
        None,
        None,
        "paid",
        clock.now(),
    )
    await uow.work.payments.insert(payment)
    service = SubscriptionService(uow, FakeStripe(), clock, "price_m", "price_y")
    for ident in (payment.id, uuid4()):
        with pytest.raises(AppError) as caught:
            await service.get_payment(other, ident)
        assert caught.value.status == 404 and caught.value.details is None
