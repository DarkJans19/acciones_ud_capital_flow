from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence.tables import kyc_accounts
from acciones_ud.wallet.domain.model import LinkedAccount


class IdentityAccountsAdapter:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: UUID) -> LinkedAccount | None:
        row = (
            (
                await self.session.execute(
                    sa.select(kyc_accounts).where(kyc_accounts.c.user_id == user_id)
                )
            )
            .mappings()
            .first()
        )
        return (
            LinkedAccount(user_id, row["alpaca_account_id"], row["status"])
            if (row and row["alpaca_account_id"])
            else None
        )

    async def list_active(self) -> list[LinkedAccount]:
        rows = (
            await self.session.execute(
                sa.select(kyc_accounts).where(
                    kyc_accounts.c.status == "ACTIVE", kyc_accounts.c.alpaca_account_id.is_not(None)
                )
            )
        ).mappings()
        return [
            LinkedAccount(row["user_id"], row["alpaca_account_id"], row["status"]) for row in rows
        ]


class AccountStatusWriter:
    async def update_status(self, user_id: UUID, status: str, at: datetime) -> None:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        async with unit_of_work() as session:
            await session.execute(
                sa.update(kyc_accounts)
                .where(kyc_accounts.c.user_id == user_id)
                .values(status=status, status_checked_at=at)
            )
