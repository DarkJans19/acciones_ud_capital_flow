import logging
from contextlib import asynccontextmanager

import pytest

from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.wallet.adapters.outbound.stripe.fake_stripe import FakeStripe
from acciones_ud.wallet.application.stripe_webhook_service import StripeWebhookService
from tests.support.clock import FakeClock
from tests.wallet.property.test_webhooks import event, signed


async def test_database_failure_is_logged_unapplied(caplog) -> None:
    @asynccontextmanager
    async def unavailable():
        raise AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Database unavailable.")
        yield

    clock = FakeClock()
    service = StripeWebhookService(unavailable, "whsec_test", FakeStripe())
    message = event("evt_unapplied", "active", int(clock.now().timestamp()))
    with caplog.at_level(logging.ERROR), pytest.raises(AppError) as caught:
        await service.handle(*signed(message, clock), clock.now())
    assert caught.value.status == 503
    record = caplog.records[-1]
    assert record.event_id == "evt_unapplied" and record.applied is False
