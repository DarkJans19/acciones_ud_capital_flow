import pytest

from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.brokers.domain.entities import LinkStatus, Period
from acciones_ud.brokers.domain.errors import (
    ConsentRequiredError,
    InvalidLinkStateError,
    LinkAlreadyExistsError,
)
from tests.brokers.support import actors, context


async def test_request_accept_expiration_and_duplicate_guard():
    ctx = context()
    investor, broker = actors(ctx)
    service = LinkService(ctx)
    first = await service.request_link(investor, broker, True)
    with pytest.raises(LinkAlreadyExistsError):
        await service.request_link(investor, broker, True)
    ctx.clock.advance(days=7)
    with pytest.raises(InvalidLinkStateError):
        await service.accept(broker, first.id)
    assert (await ctx.uow.work.links.get(id=first.id)).status == "expired"
    second = await service.request_link(investor, broker, True)
    assert (await service.accept(broker, second.id)).status == "active"
    assert len(await ctx.uow.work.events.list()) == 4


async def test_authorization_is_separate_idempotent_and_revoked_on_end():
    ctx = context()
    investor, broker = actors(ctx)
    service = LinkService(ctx)
    link = await service.request_link(investor, broker, True)
    with pytest.raises(InvalidLinkStateError):
        await service.grant_trading(investor, link.id, True)
    await service.accept(broker, link.id)
    first = await service.grant_trading(investor, link.id, True)
    assert await service.grant_trading(investor, link.id, True) == first
    await service.set_order_review(investor, link.id, True)
    ended = await service.end_link(investor, link.id, "End relationship", True)
    assert ended.status == "ended"
    assert (await ctx.uow.work.authorizations.get(id=first.id)).revoke_reason == "link_ended"


async def test_current_pending_selection_consent_and_history_period():
    ctx = context()
    investor, broker = actors(ctx)
    ctx.requests.values.add(investor)
    service = LinkService(ctx)
    current = await service.current(investor)
    assert current["link"] is None and current["trading_authorization"] is None
    assert current["pending_broker_selection"] and len(current["suggestions"]) == 1
    with pytest.raises(ConsentRequiredError):
        await service.request_link(investor, broker, False)
    link = await service.request_link(investor, broker, True)
    assert not (await service.current(investor))["pending_broker_selection"]
    assert len(await service.pending_requests(broker)) == 1
    await service.accept(broker, link.id)
    await service.set_order_review(investor, link.id, True)
    assert (await service.current(investor))["link"]["order_review_enabled"]
    today = ctx.clock.now().date()
    history = await service.history(investor, LinkStatus.ACTIVE, Period(today, today))
    assert [v["id"] for v in history["items"]] == [link.id]
    assert (await service.history(investor, LinkStatus.DECLINED))["items"] == []
