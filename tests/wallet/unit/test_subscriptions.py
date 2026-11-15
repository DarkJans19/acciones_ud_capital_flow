from dataclasses import replace
from uuid import uuid4

import pytest

from acciones_ud.shared.domain.errors import AppError
from acciones_ud.wallet.adapters.outbound.stripe.fake_stripe import FakeStripe
from acciones_ud.wallet.application.subscription_service import SubscriptionService
from acciones_ud.wallet.domain.errors import StripeUnavailableError
from tests.support.clock import FakeClock
from tests.wallet.fakes import MemoryFactory


async def test_checkout_cancel_and_failure_rollback() -> None:
    uow, stripe, clock, user = MemoryFactory(), FakeStripe(), FakeClock(), uuid4()
    service = SubscriptionService(uow, stripe, clock, "price_month", "price_year")
    assert [p.price for p in service.list_plans()] == [12, 120]
    await service.start_checkout(user, "monthly")
    pending = uow.work.subscriptions.values[0]
    active = replace(pending, status="active", stripe_subscription_id="sub_test")
    await uow.work.subscriptions.save(active)
    with pytest.raises(AppError) as caught:
        await service.start_checkout(user, "annual")
    assert caught.value.status == 409 and stripe.checkouts == 1
    stripe.failure = StripeUnavailableError()
    with pytest.raises(StripeUnavailableError):
        await service.cancel(user, "No longer needed")
    assert await uow.work.subscriptions.get(id=active.id) == active
    stripe.failure = None
    result = await service.cancel(user, "No longer needed")
    assert result.cancel_at_period_end and result.status == "active"
