from copy import deepcopy
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.application.commands import ProposalContent
from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.brokers.application.proposal_service import ProposalService
from acciones_ud.brokers.domain.errors import ExtraAuthorizationInvalidError
from tests.brokers.support import actors, context


# Feature: brokers-mod-06, Property 9: TOTP en la aceptacion
@settings(max_examples=100)
@given(
    st.integers(1, 100000),
    st.integers(1, 100),
    st.sampled_from([-1, 0, 1]),
    st.sampled_from([None, "invalid-secret", "123456"]),
)
async def test_totp_boundary_preserves_all_state_on_invalid_acceptance(
    price_cents, qty, delta, code
):
    ctx = context()
    investor, broker = actors(ctx)
    links = LinkService(ctx)
    link = await links.request_link(investor, broker, True)
    await links.accept(broker, link.id)
    ctx.quotes.price = Decimal(price_cents) / 100
    service = ProposalService(ctx)
    proposal = await service.create(
        broker, investor, ProposalContent("AAPL", "buy", Decimal(qty), "market")
    )
    version = await ctx.uow.work.versions.get(proposal_id=proposal.id, version=1)
    ctx.controls.threshold = version.estimated_cost + Decimal(delta) / 100
    before = deepcopy({k: v.values for k, v in vars(ctx.uow.work).items()})
    expected = delta > 0 or code == "123456"
    if expected:
        accepted = await service.investor_decide(investor, proposal.id, 1, "accept", totp_code=code)
        assert accepted.status == "accepted" and accepted.accepted_version == 1
    else:
        with pytest.raises(ExtraAuthorizationInvalidError):
            await service.investor_decide(investor, proposal.id, 1, "accept", totp_code=code)
        assert {k: v.values for k, v in vars(ctx.uow.work).items()} == before
    if delta > 0:
        assert not ctx.totp.calls
