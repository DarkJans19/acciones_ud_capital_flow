from decimal import Decimal
from uuid import UUID

from acciones_ud.orders.application.execution_ledger import ExecutionLedger


class ReservationReader:
    def __init__(self, ledger: ExecutionLedger) -> None:
        self.ledger = ledger

    async def active_share_reservations(self, user_id: UUID) -> dict[str, Decimal]:
        return await self.ledger.active_share_reservations(user_id)
