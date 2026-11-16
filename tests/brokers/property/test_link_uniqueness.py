import asyncio
from uuid import UUID

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.shared.domain.errors import AppError
from tests.brokers.support import context


# Feature: brokers-mod-06, Property 2: Como maximo una Link abierta por Investor
class LinkMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.ctx = context()
        self.service = LinkService(self.ctx)
        for i in range(1, 5):
            self.ctx.directory.add(UUID(int=i), "investor")
            self.ctx.directory.add(UUID(int=i), "broker")

    @rule(
        investor=st.integers(1, 4),
        broker=st.integers(1, 4),
        action=st.sampled_from(["request", "accept", "decline", "cancel", "end", "advance"]),
    )
    def operate(self, investor, broker, action):
        async def run():
            owner, selected = UUID(int=investor), UUID(int=broker)
            opened = await self.ctx.uow.work.links.open_for(owner)
            if action == "advance":
                self.ctx.clock.advance(days=7)
                return
            if action == "request":
                effective_open = opened and (
                    opened.status == "active" or opened.expires_at > self.ctx.clock.now()
                )
                expected = (
                    "VALIDATION_ERROR"
                    if owner == selected
                    else "LINK_ALREADY_EXISTS"
                    if effective_open
                    else None
                )
                try:
                    result = await self.service.request_link(owner, selected, True)
                except AppError as exc:
                    assert exc.code == expected
                else:
                    assert expected is None and result.status == "requested"
                return
            if opened is None:
                return
            try:
                if action == "accept":
                    await self.service.accept(opened.broker_id, opened.id)
                elif action == "decline":
                    await self.service.decline(opened.broker_id, opened.id, "Declined")
                elif action == "end":
                    await self.service.end_link(owner, opened.id, "Ended", True)
                else:
                    await self.service.cancel(owner, opened.id)
            except AppError as exc:
                assert exc.code == "INVALID_LINK_STATE"

        asyncio.run(run())

    @invariant()
    def at_most_one_open_link(self):
        values = list(self.ctx.uow.work.links.values.values())
        for investor in range(1, 5):
            assert (
                sum(
                    v.investor_id == UUID(int=investor) and v.status in {"requested", "active"}
                    for v in values
                )
                <= 1
            )


TestLinkUniqueness = LinkMachine.TestCase
TestLinkUniqueness.settings = settings(max_examples=100, stateful_step_count=30)
