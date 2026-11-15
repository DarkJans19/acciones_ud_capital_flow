from decimal import Decimal
from uuid import UUID

from acciones_ud.identity.application.account import AccountService
from acciones_ud.orders.domain.model import OrderControls


class IdentityControlsReader:
    def __init__(self, service: AccountService) -> None:
        self.service = service

    async def get(self, user_id: UUID) -> OrderControls:
        value = await self.service.settings(user_id, "orders")
        return OrderControls(
            str(value["default_order_type"]),
            int(value["daily_order_limit"]),
            Decimal(str(value["high_order_threshold_usd"])),
            bool(value["extra_confirmation"]),
        )
