from uuid import UUID

from acciones_ud.identity.domain.kyc_ports import KycWorkFactory
from acciones_ud.orders.domain.model import LinkedAccount


class IdentityAccountReader:
    def __init__(self, uow: KycWorkFactory) -> None:
        self.uow = uow

    async def get(self, user_id: UUID) -> LinkedAccount | None:
        async with self.uow() as work:
            value = await work.kyc.get(user_id)
        if value is None or not value.get("alpaca_account_id"):
            return None
        return LinkedAccount(user_id, str(value["alpaca_account_id"]), str(value["status"]))
