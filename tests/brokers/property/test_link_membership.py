from datetime import timedelta
from uuid import UUID, uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.domain.access import resolve_link_membership
from acciones_ud.brokers.domain.entities import Link
from acciones_ud.brokers.domain.entities import LinkStatus as S
from tests.brokers.fakes import Clock


class MemoryBrokerLinkAdapter:
    def __init__(self, links, roles):
        self.links, self.roles = links, roles

    async def is_linked(self, broker, investor):
        return any(
            item.broker_id == broker
            and item.investor_id == investor
            and item.status == S.ACTIVE
            and self.roles.get(broker, False)
            for item in self.links
        )

    async def linked_investors(self, broker):
        return [
            item.investor_id
            for item in self.links
            if await self.is_linked(broker, item.investor_id)
        ]

    async def reviewing_broker(self, investor):
        return next(
            (
                item.broker_id
                for item in self.links
                if item.investor_id == investor
                and item.status == S.ACTIVE
                and item.order_review_enabled
                and self.roles.get(item.broker_id, False)
            ),
            None,
        )


# Feature: brokers-mod-06, Property 5: Pertenencia del Broker_Link_Adapter
@settings(max_examples=100)
@given(
    st.lists(st.tuples(st.sampled_from(list(S)), st.integers(1, 3), st.booleans()), max_size=15),
    st.lists(st.booleans(), min_size=3, max_size=3),
)
async def test_membership_matches_model_and_observes_immediate_revocation(rows, flags):
    now = Clock().now()
    links = [
        Link(
            uuid4(),
            UUID(int=100 + i),
            UUID(int=b),
            status,
            now,
            now + timedelta(days=7),
            "v1",
            now,
            order_review_enabled=review,
        )
        for i, (status, b, review) in enumerate(rows)
    ]
    roles = {UUID(int=i + 1): flag for i, flag in enumerate(flags)}
    adapter = MemoryBrokerLinkAdapter(links, roles)
    expected = resolve_link_membership(links, roles)
    for broker in roles:
        assert set(await adapter.linked_investors(broker)) == expected.get(broker, set())
        for link in links:
            assert await adapter.is_linked(broker, link.investor_id) == (
                link.investor_id in expected.get(broker, set())
            )
    for link in links:
        expected_broker = (
            link.broker_id
            if link.status == S.ACTIVE and link.order_review_enabled and roles[link.broker_id]
            else None
        )
        assert await adapter.reviewing_broker(link.investor_id) == expected_broker
    for broker in roles:
        roles[broker] = False
        assert await adapter.linked_investors(broker) == []
