import asyncio
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from acciones_ud.brokers.application.commands import ProposalContent
from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.brokers.application.proposal_service import ProposalService
from acciones_ud.shared.domain.errors import AppError
from tests.brokers.support import actors, context


async def proposal_fixture():
    ctx = context()
    investor, broker = actors(ctx)
    links = LinkService(ctx)
    link = await links.request_link(investor, broker, True)
    await links.accept(broker, link.id)
    content = ProposalContent("aapl", "buy", Decimal("2"), "market")
    service = ProposalService(ctx)
    proposal = await service.create(broker, investor, content)
    return ctx, investor, broker, link, content, service, proposal


async def test_create_modify_withdraw_preserves_versions():
    ctx, investor, broker, _, content, service, proposal = await proposal_fixture()
    first = await ctx.uow.work.versions.get(proposal_id=proposal.id, version=1)
    assert first.symbol == "AAPL" and first.estimated_cost == Decimal("204.00")
    second = await service.modify(broker, proposal.id, 1, content)
    assert second.current_version == 2 and second.accepted_version is None
    assert await ctx.uow.work.versions.get(proposal_id=proposal.id, version=1) == first
    assert (await service.withdraw(broker, proposal.id, 2, "Withdrawn", True)).status == "withdrawn"


async def test_acceptance_checks_totp_without_recording_code():
    ctx, investor, broker, _, _, service, proposal = await proposal_fixture()
    ctx.controls.threshold = Decimal("204")
    before = deepcopy(ctx.uow.work.events.values)
    with pytest.raises(AppError) as caught:
        await service.investor_decide(
            investor, proposal.id, 1, "accept", totp_code="invalid-secret"
        )
    assert caught.value.code == "EXTRA_AUTHORIZATION_INVALID"
    assert ctx.uow.work.events.values == before and not ctx.uow.work.decisions.values
    accepted = await service.investor_decide(
        investor, proposal.id, 1, "accept", "Accepted", "123456"
    )
    assert accepted.status == "accepted" and accepted.accepted_version == 1
    assert "123456" not in repr(ctx.uow.work.decisions.values)
    assert "invalid-secret" not in repr(ctx.uow.work.events.values)


async def test_concurrent_approval_creates_one_order_and_one_approval_event():
    ctx, investor, broker, link, _, service, proposal = await proposal_fixture()
    await LinkService(ctx).grant_trading(investor, link.id, True)
    await service.investor_decide(investor, proposal.id, 1, "accept")
    first, second = await asyncio.gather(
        *[
            service.broker_decide(broker, proposal.id, 1, "approve", evidence_text="Approval")
            for _ in range(2)
        ]
    )
    assert first.order_id == second.order_id and first.status == "approved"
    assert len(ctx.order_creation.orders) == 1
    approved_events = [v for v in ctx.uow.work.events.values.values() if v.to_status == "approved"]
    assert len(approved_events) == 1


async def test_history_and_detail_compute_expiration_without_writes():
    ctx, investor, broker, _, _, service, proposal = await proposal_fixture()
    before = deepcopy(ctx.uow.work.events.values)
    ctx.clock.advance(hours=72)
    detail = await service.detail(investor, "investor", proposal.id)
    assert detail["status"] == "expired" and len(detail["versions"]) == 1
    assert (await ctx.uow.work.proposals.get(id=proposal.id)).status == "sent"
    assert ctx.uow.work.events.values == before
    page = await service.history_investor(investor, "expired")
    assert len(page["items"]) == 1
    assert (await service.history_broker(broker))["items"][0]["id"] == proposal.id


@pytest.mark.parametrize(
    "changes",
    [
        {"qty": Decimal(0)},
        {"qty": Decimal("NaN")},
        {"side": "invalid"},
        {"type": "stop"},
        {"type": "limit"},
        {"limit_price": Decimal(10)},
    ],
)
async def test_proposal_content_rejected_without_partial_version(changes):
    ctx, investor, broker, _, content, service, _ = await proposal_fixture()
    with pytest.raises(AppError) as caught:
        await service.create(broker, investor, replace(content, **changes))
    assert caught.value.code == "VALIDATION_ERROR"
    assert len(ctx.uow.work.proposals.values) == len(ctx.uow.work.versions.values) == 1


async def test_quotes_accounts_and_evidence_are_checked():
    ctx, investor, broker, _, content, service, proposal = await proposal_fixture()
    ctx.quotes.price = None
    with pytest.raises(AppError) as caught:
        await service.create(broker, investor, content)
    assert caught.value.code == "QUOTE_UNAVAILABLE"
    limit = await service.create(
        broker, investor, replace(content, type="limit", limit_price=Decimal(99))
    )
    assert limit.status == "sent"
    ctx.accounts.linked.clear()
    with pytest.raises(AppError) as caught:
        await service.create(broker, investor, content)
    assert caught.value.code == "ACCOUNT_NOT_LINKED"
    ctx.accounts.linked.add(investor)
    await service.investor_decide(investor, proposal.id, 1, "accept")
    with pytest.raises(AppError) as caught:
        await service.broker_decide(broker, proposal.id, 1, "approve", (uuid4(),))
    assert caught.value.code == "VALIDATION_ERROR" and not ctx.order_creation.creation_calls
    declined = await service.broker_decide(
        broker, proposal.id, 1, "decline", evidence_text="Declined"
    )
    assert declined.status == "declined_by_broker"


async def test_link_end_during_conversion_records_orphan_order_without_reopening_proposal():
    ctx, investor, broker, link, _, service, proposal = await proposal_fixture()
    await LinkService(ctx).grant_trading(investor, link.id, True)
    await service.investor_decide(investor, proposal.id, 1, "accept")

    async def end_link():
        await LinkService(ctx).end_link(investor, link.id, "Ended during conversion", True)

    ctx.order_creation.after_create = end_link
    with pytest.raises(AppError) as caught:
        await service.broker_decide(broker, proposal.id, 1, "approve")
    assert caught.value.code == "INVALID_PROPOSAL_STATE"
    final = await ctx.uow.work.proposals.get(id=proposal.id)
    assert final.status == "withdrawn" and final.order_id is None
    assert len(ctx.order_creation.orders) == 1
    assert any(event.details.get("orphan_order") for event in ctx.uow.work.events.values.values())


async def test_estimate_overflow_is_rejected_before_writing_a_version():
    ctx, investor, broker, _, content, service, _ = await proposal_fixture()
    with pytest.raises(AppError) as caught:
        await service.create(
            broker,
            investor,
            replace(content, qty=Decimal("1e10"), type="limit", limit_price=Decimal("1e10")),
        )
    assert caught.value.code == "VALIDATION_ERROR"
    assert caught.value.details["field"] == "estimated_cost"
    assert len(ctx.uow.work.versions.values) == 1
