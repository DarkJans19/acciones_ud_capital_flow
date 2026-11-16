import asyncio
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from acciones_ud.brokers.adapters.inbound.jobs.expiry_job import ExpiryJob
from acciones_ud.brokers.application.expiry_service import ExpiryService
from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.brokers.unit.test_proposals import proposal_fixture


async def test_expiry_handles_both_categories_once_in_same_cycle():
    ctx, _, broker, _, _, _, proposal = await proposal_fixture()
    investor = uuid4()
    ctx.directory.add(investor, "investor")
    requested = await LinkService(ctx).request_link(investor, broker, True)
    ctx.clock.advance(days=7)
    before = len(ctx.notifier.calls)
    service = ExpiryService(ctx)
    await service.run_once(ctx.clock.now())
    assert (await ctx.uow.work.links.get(id=requested.id)).status == "expired"
    assert (await ctx.uow.work.proposals.get(id=proposal.id)).status == "expired"
    assert len(ctx.notifier.calls) == before + 3
    events = dict(ctx.uow.work.events.values)
    await service.run_once()
    assert ctx.uow.work.events.values == events and len(ctx.notifier.calls) == before + 3


async def test_reconciliation_recovers_order_after_second_transaction_failure():
    ctx, investor, broker, link, _, proposals, proposal = await proposal_fixture()
    await LinkService(ctx).grant_trading(investor, link.id, True)
    await proposals.investor_decide(investor, proposal.id, 1, "accept")
    ctx.uow.work.proposals.fail_save = True
    with pytest.raises(RuntimeError):
        await proposals.broker_decide(broker, proposal.id, 1, "approve", evidence_text="Evidence")
    assert (await ctx.uow.work.proposals.get(id=proposal.id)).status == "accepted"
    assert len(ctx.order_creation.orders) == 1
    ctx.uow.work.proposals.fail_save = False
    ctx.clock.advance(days=4)
    await ExpiryService(ctx).run_once()
    final = await ctx.uow.work.proposals.get(id=proposal.id)
    assert final.status == "approved" and final.order_id == next(
        iter(ctx.order_creation.orders.values())
    )
    assert len(ctx.order_creation.creation_calls) == 1
    calls = len(ctx.order_query.query_calls)
    await ExpiryService(ctx).run_once()
    assert len(ctx.order_query.query_calls) == calls


async def test_reconciliation_does_not_attach_an_order_with_different_content():
    ctx, investor, broker, link, _, proposals, proposal = await proposal_fixture()
    await LinkService(ctx).grant_trading(investor, link.id, True)
    await proposals.investor_decide(investor, proposal.id, 1, "accept")
    ctx.order_creation.failure = AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Unavailable")
    with pytest.raises(AppError):
        await proposals.broker_decide(broker, proposal.id, 1, "approve")
    original = ctx.order_creation.creation_calls[-1]
    key = investor, f"proposal:{proposal.id}"
    ctx.order_creation.orders[key] = uuid4()
    ctx.order_creation.commands[key] = replace(original, qty=Decimal(999))
    ctx.clock.advance(days=4)
    await ExpiryService(ctx).run_once()
    assert (await ctx.uow.work.proposals.get(id=proposal.id)).status == "accepted"


async def test_expiry_job_retries_after_failure_and_stops_cleanly():
    entered = asyncio.Event()

    class Work:
        calls = 0

        async def run_once(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Transient failure")
            entered.set()

    work = Work()
    job = ExpiryJob(work, 0.001, "brokers-test")
    job.start()
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert work.calls >= 2
        task = job.task
    finally:
        await job.stop()
    assert task.done() and job.task is None


async def test_notification_failure_does_not_roll_back_transition():
    ctx, investor, _, link, _, _, _ = await proposal_fixture()
    ctx.notifier.fail = True
    assert (await LinkService(ctx).end_link(investor, link.id, "Ended", True)).status == "ended"
