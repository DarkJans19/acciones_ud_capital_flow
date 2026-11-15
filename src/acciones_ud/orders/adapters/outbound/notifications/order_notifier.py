from uuid import UUID

from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.domain.ports import DirectoryFactory
from acciones_ud.orders.domain.ports import OrderEventType


class OrderNotifierAdapter:
    def __init__(self, directory: DirectoryFactory, notifier: Notifier) -> None:
        self.directory, self.notifier = directory, notifier

    async def notify(
        self, user_id: UUID, event_type: OrderEventType, payload: dict[str, object]
    ) -> None:
        async with self.directory() as directory:
            recipient = await directory.recipient(user_id, event_type)
        if recipient is not None:
            await self.notifier.notify([recipient], event_type, payload)
