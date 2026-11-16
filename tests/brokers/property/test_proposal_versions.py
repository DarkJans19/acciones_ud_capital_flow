from copy import deepcopy
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.domain.entities import ProposalStatus as S
from acciones_ud.shared.domain.errors import AppError
from tests.brokers.unit.test_proposals import proposal_fixture


# Feature: brokers-mod-06, Property 8: Control de version de la Proposal
@settings(max_examples=100)
@given(
    st.booleans(),
    st.lists(
        st.tuples(st.sampled_from(["modify", "withdraw", "accept", "reject"]), st.integers(-1, 1)),
        max_size=25,
    ),
)
async def test_proposal_versions_are_consecutive_immutable_and_checked_after_state(
    accepted, actions
):
    ctx, investor, broker, _, content, service, proposal = await proposal_fixture()
    if accepted:
        proposal = replace(proposal, status=S.ACCEPTED, accepted_version=1)
        await ctx.uow.work.proposals.save(proposal)
    saved_versions = {}
    for action, offset in actions:
        current = await ctx.uow.work.proposals.get(id=proposal.id)
        seen = current.current_version + offset
        previous = deepcopy(ctx.uow.work.versions.values)
        expected = (
            "INVALID_PROPOSAL_STATE"
            if current.status
            not in ({S.SENT} if action in {"accept", "reject"} else {S.SENT, S.ACCEPTED})
            else "PROPOSAL_VERSION_CONFLICT"
            if offset
            else None
        )
        try:
            if action == "modify":
                updated = await service.modify(broker, proposal.id, seen, content)
                assert updated.current_version == current.current_version + 1
                assert updated.status == S.SENT and updated.accepted_version is None
            elif action == "withdraw":
                await service.withdraw(broker, proposal.id, seen, "Withdrawn", True)
            else:
                updated = await service.investor_decide(investor, proposal.id, seen, action)
                assert updated.accepted_version == (seen if action == "accept" else None)
        except AppError as exc:
            assert exc.code == expected
            assert await ctx.uow.work.proposals.get(id=proposal.id) == current
        else:
            assert expected is None
        for key, value in previous.items():
            assert ctx.uow.work.versions.values[key] == value
        for key, value in saved_versions.items():
            assert ctx.uow.work.versions.values[key] == value
        saved_versions.update(ctx.uow.work.versions.values)
