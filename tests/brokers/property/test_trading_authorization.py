from datetime import timedelta
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.brokers.domain.entities import Link
from acciones_ud.brokers.domain.entities import LinkStatus as S
from acciones_ud.shared.domain.errors import AppError
from tests.brokers.support import actors, context


# Feature: brokers-mod-06, Property 4: Trading_Authorization unica y ligada a la Active_Link
@settings(max_examples=100)
@given(
    st.sampled_from(list(S)),
    st.lists(st.sampled_from(["grant", "revoke", "accept", "end"]), max_size=35),
)
async def test_authorization_sequences(initial, actions):
    ctx = context()
    investor, broker = actors(ctx)
    now = ctx.clock.now()
    link = Link(uuid4(), investor, broker, initial, now, now + timedelta(days=7), "v1", now)
    await ctx.uow.work.links.insert(link)
    service = LinkService(ctx)
    for action in actions:
        current = await ctx.uow.work.links.get(id=link.id)
        existing = await ctx.uow.work.authorizations.get(link_id=link.id, revoked_at=None)
        try:
            if action == "grant":
                result = await service.grant_trading(investor, link.id, True)
                assert current.status == S.ACTIVE
                if existing:
                    assert result.id == existing.id
            elif action == "revoke":
                result = await service.revoke_trading(investor, link.id)
                assert result.revoked_at == ctx.clock.now() and existing
            elif action == "accept":
                await service.accept(broker, link.id)
            else:
                await service.end_link(investor, link.id, "Ended", True)
        except AppError as exc:
            assert exc.code == "INVALID_LINK_STATE"
            assert (
                (action == "grant" and current.status != S.ACTIVE)
                or (action == "revoke" and existing is None)
                or (action == "accept" and current.status != S.REQUESTED)
                or (action == "end" and current.status != S.ACTIVE)
            )
        active = [a for a in ctx.uow.work.authorizations.values.values() if a.revoked_at is None]
        assert len(active) <= 1
        assert not active or (await ctx.uow.work.links.get(id=link.id)).status == S.ACTIVE
