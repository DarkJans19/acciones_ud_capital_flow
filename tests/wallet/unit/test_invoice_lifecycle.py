from tests.wallet.property.test_webhooks import setup_webhook, signed


async def test_failed_invoice_can_later_be_paid_without_duplicate_payment() -> None:
    uow, clock, user, handler = await setup_webhook()
    invoice = {
        "id": "in_same_invoice",
        "subscription": "sub_test",
        "customer": "cus_test",
        "amount_due": 1200,
        "amount_paid": 0,
        "currency": "usd",
    }
    failed = {
        "id": "evt_failed",
        "type": "invoice.payment_failed",
        "created": int(clock.now().timestamp()),
        "data": {"object": dict(invoice)},
    }
    await handler.handle(*signed(failed, clock), clock.now())
    assert uow.work.payments.values[0].result == "failed"
    payment_id = uow.work.payments.values[0].id
    clock.advance(2)
    invoice["amount_paid"] = 1200
    paid = {
        "id": "evt_paid",
        "type": "invoice.paid",
        "created": int(clock.now().timestamp()),
        "data": {"object": invoice},
    }
    await handler.handle(*signed(paid, clock), clock.now())
    assert len(uow.work.payments.values) == 1
    payment = uow.work.payments.values[0]
    assert payment.id == payment_id and payment.result == "paid" and payment.amount == 12
    failed["id"] = "evt_late_failure"
    await handler.handle(*signed(failed, clock), clock.now())
    assert uow.work.payments.values[0] == payment
