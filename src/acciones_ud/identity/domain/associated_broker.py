from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AssociatedBroker:
    id: UUID
    name: str
    firm_name: str
    since: datetime


class AssociatedBrokerReader(Protocol):
    async def associated_broker(self, investor_id: UUID) -> AssociatedBroker | None: ...
