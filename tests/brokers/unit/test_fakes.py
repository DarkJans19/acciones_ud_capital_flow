from datetime import timedelta
from uuid import uuid4

import pytest

from acciones_ud.brokers.domain.entities import Link, LinkStatus
from acciones_ud.brokers.domain.errors import LinkAlreadyExistsError
from tests.brokers.fakes import Clock, MemoryFactory


async def test_reference_repositories_enforce_uniqueness_and_transaction_rollback():
    factory, clock = MemoryFactory(), Clock()
    now = clock.now()
    link = Link(
        uuid4(), uuid4(), uuid4(), LinkStatus.ACTIVE, now, now + timedelta(days=7), "v1", now
    )
    async with factory() as work:
        await work.links.insert(link)
    with pytest.raises(LinkAlreadyExistsError):
        async with factory() as work:
            await work.links.insert(
                Link(
                    uuid4(),
                    link.investor_id,
                    uuid4(),
                    LinkStatus.REQUESTED,
                    now,
                    now + timedelta(days=7),
                    "v1",
                    now,
                )
            )
    assert len(factory.work.links.values) == 1
    with pytest.raises(RuntimeError):
        async with factory() as work:
            work.links.values.clear()
            raise RuntimeError("Rollback")
    assert await factory.work.links.get(id=link.id) == link
