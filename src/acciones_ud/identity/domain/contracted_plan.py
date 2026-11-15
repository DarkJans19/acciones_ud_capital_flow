from typing import Literal, Protocol
from uuid import UUID


class ContractedPlanReader(Protocol):
    async def get(self, user_id: UUID) -> Literal["monthly", "annual"] | None: ...
