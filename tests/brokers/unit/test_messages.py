import pytest

from acciones_ud.brokers.application.message_service import MessageService
from acciones_ud.brokers.domain.errors import ValidationError
from tests.brokers.unit.test_proposals import proposal_fixture


async def test_messages_are_chronological_paginated_and_validate_body():
    ctx, investor, broker, _, _, _, proposal = await proposal_fixture()
    service = MessageService(ctx)
    for body in ("", " " * 3, "x" * 1001):
        with pytest.raises(ValidationError):
            await service.post(investor, "investor", proposal.id, body)
    first = await service.post(investor, "investor", proposal.id, "Investor evidence")
    ctx.clock.advance(seconds=1)
    second = await service.post(broker, "broker", proposal.id, "Broker evidence")
    page = await service.thread(investor, "investor", proposal.id, page_size=1)
    assert page["items"][0]["id"] == first.id and page["next_cursor"]
    following = await service.thread(broker, "broker", proposal.id, page["next_cursor"], 1)
    assert following["items"][0]["id"] == second.id and following["next_cursor"] is None
