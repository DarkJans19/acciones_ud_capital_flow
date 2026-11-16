from decimal import Decimal
from uuid import UUID

from acciones_ud.identity.application.account import AccountService


class ControlsReader:
    def __init__(self, service: AccountService) -> None:
        self.service = service

    async def high_order_threshold_usd(self, investor_id: UUID) -> Decimal:
        settings = await self.service.settings(investor_id, "orders")
        return Decimal(str(settings["high_order_threshold_usd"]))
