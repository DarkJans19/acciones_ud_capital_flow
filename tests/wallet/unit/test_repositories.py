from datetime import UTC, datetime
from uuid import uuid4

from acciones_ud.wallet.domain.model import IdempotencyEntry
from tests.wallet.fakes import MemoryFactory


async def test_conditional_update_and_unique_insert() -> None:
    factory = MemoryFactory()
    entry = IdempotencyEntry(uuid4(), "key12345", "hash", "in_progress", None, datetime.now(UTC))
    async with factory() as work:
        assert await work.keys.insert(entry)
        assert not await work.keys.insert(entry)
        assert not await work.keys.save(entry, state="completed")
        assert await work.keys.save(entry, state="in_progress")


async def test_transaction_rolls_back() -> None:
    factory = MemoryFactory()
    user_id = uuid4()
    try:
        async with factory() as work:
            await work.premium.set_premium(user_id, True)
            raise ValueError()
    except ValueError:
        pass
    assert not factory.work.premium.values
