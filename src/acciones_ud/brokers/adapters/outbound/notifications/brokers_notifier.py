import logging
from collections.abc import Mapping
from uuid import UUID

from acciones_ud.brokers.domain.entities import EventType
from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.domain.ports import DirectoryFactory

logger = logging.getLogger(__name__)


class BrokersNotifier:
    def __init__(self, directory: DirectoryFactory, notifier: Notifier) -> None:
        self.directory, self.notifier = directory, notifier

    async def notify(
        self, user_id: UUID, event_type: EventType, payload: Mapping[str, object]
    ) -> None:
        try:
            async with self.directory() as directory:
                recipient = await directory.recipient(user_id, event_type)
            if recipient is not None:
                await self.notifier.notify([recipient], event_type, dict(payload))
        except Exception:
            logger.warning(
                "Broker notification delivery failed",
                extra={"user_id": str(user_id), "event_type": event_type},
            )
