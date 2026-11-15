from typing import Literal
from uuid import UUID

from acciones_ud.wallet.domain.ports import WalletWorkFactory


class ContractedPlanReader:
    def __init__(self, uow: WalletWorkFactory) -> None:
        self.uow = uow

    async def get(self, user_id: UUID) -> Literal["monthly", "annual"] | None:
        async with self.uow() as work:
            values = await work.subscriptions.list(user_id=user_id)
            return next(
                (v.plan for v in values if v.status in {"active", "trialing", "past_due"}), None
            )
