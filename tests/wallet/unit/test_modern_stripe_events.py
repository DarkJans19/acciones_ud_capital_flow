from datetime import UTC, datetime

import pytest

from tests.wallet.property.test_webhooks import event, setup_webhook, signed


@pytest.mark.parametrize("modern", [False, True])
async def test_both_subscription_period_formats_persist_exact_dates(modern: bool) -> None:
    uow, clock, _, handler = await setup_webhook()
    message = event("evt_period", "active", int(clock.now().timestamp()))
    period = {"current_period_start": 1800000000, "current_period_end": 1802678400}
    data = message["data"]["object"]
    if modern:
        data["items"] = {"data": [{"id": "si_test", **period}]}
    else:
        data.update(period)
    await handler.handle(*signed(message, clock), clock.now())
    subscription = uow.work.subscriptions.values[0]
    assert subscription.current_period_start == datetime.fromtimestamp(1800000000, UTC)
    assert subscription.current_period_end == datetime.fromtimestamp(1802678400, UTC)


async def test_modern_invoice_matches_subscription_without_customer_fallback() -> None:
    uow, clock, _, handler = await setup_webhook()
    message = {
        "id": "evt_modern_invoice",
        "type": "invoice.paid",
        "created": int(clock.now().timestamp()),
        "data": {
            "object": {
                "id": "in_modern",
                "customer": "different-customer",
                "parent": {
                    "type": "subscription_details",
                    "subscription_details": {"subscription": "sub_test"},
                },
                "amount_paid": 1200,
                "currency": "usd",
                "lines": {"data": [{"period": {"start": 1800000000, "end": 1802678400}}]},
            }
        },
    }
    await handler.handle(*signed(message, clock), clock.now())
    await handler.handle(*signed(message, clock), clock.now())
    assert len(uow.work.payments.values) == 1
    assert str(uow.work.payments.values[0].amount) == "12"
    assert uow.work.payments.values[0].result == "paid"


async def test_invoice_with_null_parent_is_ignored_when_unassociated() -> None:
    uow, clock, _, handler = await setup_webhook()
    message = {
        "id": "evt_unrelated_invoice",
        "type": "invoice.paid",
        "created": int(clock.now().timestamp()),
        "data": {"object": {"id": "in_unrelated", "parent": None}},
    }
    await handler.handle(*signed(message, clock), clock.now())
    assert not uow.work.payments.values
    assert uow.work.events.values[0].outcome == "unassociated"
