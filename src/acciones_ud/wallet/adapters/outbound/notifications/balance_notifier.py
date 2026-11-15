from uuid import UUID

from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.domain.ports import DirectoryFactory


class BalanceNotifierAdapter:
    def __init__(self, directory: DirectoryFactory, notifier: Notifier) -> None:
        self.directory, self.notifier = directory, notifier

    async def notify(self, user_id: UUID, payload: dict[str, object]) -> None:
        async with self.directory() as work:
            recipient = await work.recipient(user_id, "balance_changes")
        if recipient is not None:
            await self.notifier.notify([recipient], "balance_changes", payload)
