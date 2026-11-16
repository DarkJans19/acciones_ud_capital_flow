from uuid import UUID

from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.domain.ports import DirectoryFactory


class ReportNotifier:
    def __init__(self, directory: DirectoryFactory, notifier: Notifier) -> None:
        self.directory, self.notifier = directory, notifier

    async def notify(self, user_id: UUID, payload: dict[str, object]) -> bool:
        async with self.directory() as work:
            recipient = await work.recipient(user_id, "daily_summary")
        if recipient is None:
            return False
        return bool(await self.notifier.notify([recipient], "daily_summary", payload))
