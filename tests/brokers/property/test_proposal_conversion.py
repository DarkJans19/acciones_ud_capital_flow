import asyncio

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.brokers.unit.test_proposals import proposal_fixture


# Feature: brokers-mod-06, Property 10: Conversion en Order exactamente una vez
@settings(max_examples=100)
@given(
    st.booleans(),
    st.lists(
        st.tuples(
            st.sampled_from(["success", "rejected", "alpaca", "rate", "database"]),
            st.integers(1, 3),
        ),
        min_size=1,
        max_size=10,
    ),
)
async def test_conversion_is_idempotent_and_preserves_accepted_on_unavailability(
    authorized, actions
):
    ctx, investor, broker, link, _, service, proposal = await proposal_fixture()
    await service.investor_decide(investor, proposal.id, 1, "accept")
    if authorized:
        await LinkService(ctx).grant_trading(investor, link.id, True)
    approved_id = None
    for outcome, repetitions in actions:
        current = await ctx.uow.work.proposals.get(id=proposal.id)
        ctx.order_creation.rejection = (
            "INSUFFICIENT_BUYING_POWER" if outcome == "rejected" else None
        )
        errors = {
            "alpaca": (502, ErrorCode.ALPACA_UNAVAILABLE),
            "rate": (503, ErrorCode.ALPACA_RATE_LIMITED),
            "database": (503, ErrorCode.DATABASE_UNAVAILABLE),
        }
        ctx.order_creation.failure = (
            AppError(*errors[outcome], "Unavailable") if outcome in errors else None
        )
        previous_calls = len(ctx.order_creation.creation_calls)
        responses = await asyncio.gather(
            *[
                service.broker_decide(broker, proposal.id, 1, "approve", evidence_text="Evidence")
                for _ in range(repetitions)
            ],
            return_exceptions=True,
        )
        latest = await ctx.uow.work.proposals.get(id=proposal.id)
        if current.status == "approved":
            assert len(ctx.order_creation.creation_calls) == previous_calls
            assert all(r.order_id == approved_id for r in responses)
        elif current.status == "conversion_failed":
            assert all(
                isinstance(r, AppError) and r.code == "INVALID_PROPOSAL_STATE" for r in responses
            )
        elif not authorized:
            assert all(
                isinstance(r, AppError) and r.code == "TRADING_AUTHORIZATION_REQUIRED"
                for r in responses
            )
            assert len(ctx.order_creation.creation_calls) == 0 and latest == current
        elif outcome in errors:
            assert latest.status == "accepted" and latest.order_id is None
            assert all(isinstance(r, AppError) and r.code == errors[outcome][1] for r in responses)
        elif outcome == "rejected":
            assert latest.status == "conversion_failed" and latest.order_id is None
            assert latest.failure_code == "INSUFFICIENT_BUYING_POWER"
        else:
            assert latest.status == "approved" and latest.order_id
            approved_id = latest.order_id
            assert all(r.order_id == approved_id for r in responses)
        assert len(ctx.order_creation.orders) <= 1
