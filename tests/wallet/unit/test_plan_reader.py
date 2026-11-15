from uuid import uuid4

from acciones_ud.wallet.adapters.outbound.identity.contracted_plan_reader import (
    ContractedPlanReader,
)
from acciones_ud.wallet.domain.model import Subscription
from tests.wallet.fakes import MemoryFactory


async def test_current_plan() -> None:
    factory = MemoryFactory()
    user_id = uuid4()
    reader = ContractedPlanReader(factory)
    assert await reader.get(user_id) is None
    await factory.work.subscriptions.insert(
        Subscription(uuid4(), user_id, "monthly", "active", "cs")
    )
    assert await reader.get(user_id) == "monthly"
    assert await reader.get(uuid4()) is None
