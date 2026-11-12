from datetime import datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence.tables import kyc_accounts
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.kyc import AlpacaAccount
from acciones_ud.shared.domain.clock import Clock


class KycRepository:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self.session, self.clock = session, clock

    async def get(self, user_id: UUID) -> Record | None:
        row = (
            (
                await self.session.execute(
                    sa.select(kyc_accounts).where(kyc_accounts.c.user_id == user_id)
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    async def record_status_check(self, account: AlpacaAccount, retrieved_at: datetime) -> None:
        # One conditional UPDATE: the guard never moves the check backwards, and the
        # CASE changes status and status_updated_at only when the status differs (23.5).
        await self.session.execute(
            kyc_accounts.update()
            .where(
                kyc_accounts.c.alpaca_account_id == account.id,
                sa.or_(
                    kyc_accounts.c.status_checked_at.is_(None),
                    kyc_accounts.c.status_checked_at <= retrieved_at,
                ),
            )
            .values(
                status_checked_at=retrieved_at,
                status_updated_at=sa.case(
                    (
                        kyc_accounts.c.status.is_distinct_from(account.status),
                        account.updated_at or retrieved_at,
                    ),
                    else_=kyc_accounts.c.status_updated_at,
                ),
                status=account.status,
            )
        )

    async def linked_account_ids(self) -> list[str]:
        result = await self.session.execute(
            sa.select(kyc_accounts.c.alpaca_account_id).where(
                kyc_accounts.c.alpaca_account_id.is_not(None)
            )
        )
        values: list[str] = list(result.scalars())
        return values

    async def reserve(self, user_id: UUID, now: datetime) -> bool:
        result = await self.session.execute(
            insert(kyc_accounts)
            .values(user_id=user_id, reserved_at=now)
            .on_conflict_do_update(
                index_elements=[kyc_accounts.c.user_id],
                set_={"reserved_at": now},
                where=sa.and_(
                    kyc_accounts.c.alpaca_account_id.is_(None),
                    kyc_accounts.c.reserved_at < now - timedelta(seconds=120),
                ),
            )
            .returning(kyc_accounts.c.user_id)
        )
        return result.first() is not None

    async def complete(
        self, user_id: UUID, reservation: datetime, account: AlpacaAccount, tax_last4: str
    ) -> bool:
        result = await self.session.execute(
            kyc_accounts.update()
            .where(
                kyc_accounts.c.user_id == user_id,
                kyc_accounts.c.reserved_at == reservation,
                kyc_accounts.c.alpaca_account_id.is_(None),
            )
            .values(
                alpaca_account_id=account.id,
                status=account.status,
                status_updated_at=account.updated_at or self.clock.now(),
                tax_id_last4=tax_last4,
            )
            .returning(kyc_accounts.c.user_id)
        )
        return result.first() is not None

    async def release(self, user_id: UUID, reservation: datetime) -> None:
        await self.session.execute(
            kyc_accounts.delete().where(
                kyc_accounts.c.user_id == user_id,
                kyc_accounts.c.reserved_at == reservation,
                kyc_accounts.c.alpaca_account_id.is_(None),
            )
        )
