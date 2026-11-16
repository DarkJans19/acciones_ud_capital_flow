from copy import deepcopy
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.brokers.domain.entities import Proposal
from acciones_ud.brokers.domain.entities import ProposalStatus as S
from acciones_ud.brokers.domain.errors import ConfirmationRequiredError
from tests.brokers.support import actors, context


# Feature: brokers-mod-06, Property 3: Cascada del fin de la Link
@settings(max_examples=100)
@given(st.lists(st.sampled_from(list(S)), max_size=12), st.booleans(), st.booleans(), st.booleans())
async def test_link_end_cascade_and_atomic_rollback(statuses, authorized, confirmed, failure):
    ctx = context()
    investor, broker = actors(ctx)
    service = LinkService(ctx)
    link = await service.request_link(investor, broker, True)
    await service.accept(broker, link.id)
    if authorized:
        await service.grant_trading(investor, link.id, True)
    now = ctx.clock.now()
    for status in statuses:
        await ctx.uow.work.proposals.insert(
            Proposal(
                uuid4(),
                link.id,
                broker,
                investor,
                status,
                1,
                now,
                now,
                now,
                now,
                order_id=uuid4() if status == S.APPROVED else None,
            )
        )
    ctx.uow.work.authorizations.fail_save = failure
    before = deepcopy({k: v.values for k, v in vars(ctx.uow.work).items()})
    if not confirmed or (authorized and failure):
        with pytest.raises(ConfirmationRequiredError if not confirmed else RuntimeError):
            await service.end_link(investor, link.id, "Relationship ended", confirmed)
        assert {k: v.values for k, v in vars(ctx.uow.work).items()} == before
        return
    result = await service.end_link(investor, link.id, "Relationship ended", True)
    assert result.status == "ended" and result.ended_at == now
    assert result.end_reason == "Relationship ended"
    assert len(ctx.uow.work.links.values) == 1
    for ident, old in before["proposals"].items():
        latest = ctx.uow.work.proposals.values[ident]
        if old.status in {S.SENT, S.ACCEPTED}:
            assert latest.status == S.WITHDRAWN and latest.status_reason == "link_ended"
        else:
            assert latest == old
    assert all(
        a.revoked_at == now and a.revoke_reason == "link_ended"
        for a in ctx.uow.work.authorizations.values.values()
    )
    changed = sum(s in {S.SENT, S.ACCEPTED} for s in statuses)
    assert len(ctx.uow.work.events.values) == len(before["events"]) + 1 + authorized + changed
