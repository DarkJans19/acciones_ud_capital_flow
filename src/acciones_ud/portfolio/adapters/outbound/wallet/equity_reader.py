from decimal import Decimal, InvalidOperation

import sqlalchemy as sa

from acciones_ud.identity.adapters.outbound.persistence.tables import kyc_accounts
from acciones_ud.shared.domain.errors import AppError
from acciones_ud.wallet.application.wallet_service import WalletService


class EquityReader:
    def __init__(self, wallet: WalletService) -> None:
        self.wallet = wallet

    async def equity(self, alpaca_account_id: str) -> Decimal | None:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        try:
            async with unit_of_work() as session:
                user_id = (
                    await session.execute(
                        sa.select(kyc_accounts.c.user_id).where(
                            kyc_accounts.c.alpaca_account_id == alpaca_account_id,
                            kyc_accounts.c.status == "ACTIVE",
                        )
                    )
                ).scalar_one_or_none()
            if user_id is None:
                return None
            balance = await self.wallet.get_balances(user_id)
            if balance.unavailable or balance.status != "ACTIVE" or balance.equity is None:
                return None
            equity = Decimal(balance.equity)
            return equity if equity.is_finite() and equity >= 0 else None
        except (AppError, InvalidOperation):
            return None
