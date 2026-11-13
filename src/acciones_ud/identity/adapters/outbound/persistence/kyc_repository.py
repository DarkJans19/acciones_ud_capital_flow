from datetime import datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence.tables import kyc_accounts, users
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.kyc import AlpacaAccount
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


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

    async def user_email(self, user_id: UUID) -> str:
        email = (
            await self.session.execute(
                sa.select(users.c.email).where(users.c.id == user_id)
            )
        ).scalar_one_or_none()
        if email is None:
            raise AppError(404, ErrorCode.NOT_FOUND, "User not found.", {"resource": "user"})
        return str(email)

    async def get_by_alpaca_id(self, account_id: str) -> Record | None:
        row = (
            (
                await self.session.execute(
                    sa.select(kyc_accounts).where(
                        kyc_accounts.c.alpaca_account_id == account_id
                    )
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    async def link_new(
        self, user_id: UUID, account_id: str, status: str, retrieved_at: datetime
    ) -> bool:
        result = await self.session.execute(
            insert(kyc_accounts)
            .values(
                user_id=user_id,
                alpaca_account_id=account_id,
                status=status,
                status_updated_at=retrieved_at,
                status_checked_at=retrieved_at,
                reserved_at=retrieved_at,
                tax_id_last4=None,
            )
            .on_conflict_do_nothing()
            .returning(kyc_accounts.c.user_id)
        )
        return result.first() is not None

    async def link_reserved(
        self,
        user_id: UUID,
        account_id: str,
        status: str,
        retrieved_at: datetime,
        observed_reserved_at: datetime,
    ) -> bool:
        try:
            async with self.session.begin_nested():
                result = await self.session.execute(
                    kyc_accounts.update()
                    .where(
                        kyc_accounts.c.user_id == user_id,
                        kyc_accounts.c.alpaca_account_id.is_(None),
                        kyc_accounts.c.reserved_at == observed_reserved_at,
                    )
                    .values(
                        alpaca_account_id=account_id,
                        status=status,
                        status_updated_at=retrieved_at,
                        status_checked_at=retrieved_at,
                    )
                    .returning(kyc_accounts.c.user_id)
                )
        except IntegrityError:
            # A unique violation on alpaca_account_id becomes 409 in the use case.
            return False
        return result.first() is not None

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
