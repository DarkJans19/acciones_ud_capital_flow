import re
from dataclasses import replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from acciones_ud.shared.domain.alpaca_errors import (
    AlpacaError,
    AlpacaValidationError,
    to_app_error,
)
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.wallet.application.dtos import Page, invalid, paginate, period, timestamp
from acciones_ud.wallet.domain.idempotency import request_hash
from acciones_ud.wallet.domain.model import (
    BankRelationship,
    BankRelationshipInput,
    Direction,
    IdempotencyEntry,
    LinkedAccount,
    Transfer,
)
from acciones_ud.wallet.domain.money import parse_transfer_amount, validate_currency
from acciones_ud.wallet.domain.ports import AlpacaFundingPort, WalletWorkFactory
from acciones_ud.wallet.domain.transfers import check_withdrawable


def not_found() -> AppError:
    return AppError(404, ErrorCode.NOT_FOUND, "Resource not found.")


class FundingService:
    def __init__(
        self, uow: WalletWorkFactory, alpaca: AlpacaFundingPort, clock: Clock, maximum: Decimal
    ) -> None:
        self.uow, self.alpaca, self.clock, self.maximum = uow, alpaca, clock, maximum

    async def _linked(self, user_id: UUID, *, active: bool = False) -> LinkedAccount:
        async with self.uow() as work:
            linked = await work.accounts.get(user_id)
        if linked is None:
            raise AppError(409, ErrorCode.WALLET_ACCOUNT_REQUIRED, "Linked account required.")
        if active and not linked.is_active:
            raise AppError(
                409,
                ErrorCode.WALLET_ACCOUNT_NOT_ACTIVE,
                "Active account required.",
                {"status": linked.status},
            )
        return linked

    async def create_bank_relationship(
        self, user_id: UUID, data: BankRelationshipInput
    ) -> BankRelationship:
        fields = []
        if not 1 <= len(data.account_owner_name.strip()) <= 200:
            fields.append("account_owner_name")
        if data.bank_account_type not in {"CHECKING", "SAVINGS"}:
            fields.append("bank_account_type")
        if not re.fullmatch(r"[0-9]{4,17}", data.bank_account_number):
            fields.append("bank_account_number")
        if not re.fullmatch(r"[0-9]{9}", data.bank_routing_number):
            fields.append("bank_routing_number")
        if fields:
            raise invalid(*fields)
        account = await self._linked(user_id, active=True)
        try:
            raw = await self.alpaca.create_ach_relationship(account.alpaca_account_id, data)
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        bank = BankRelationship(
            uuid4(),
            user_id,
            account.alpaca_account_id,
            str(raw["id"]),
            data.account_owner_name,
            data.bank_account_type,
            data.bank_account_number[-4:],
            str(raw["status"]),
            timestamp(raw.get("created_at")) or self.clock.now(),
        )
        async with self.uow() as work:
            await work.banks.insert(bank)
        return bank

    async def list_bank_relationships(self, user_id: UUID) -> list[BankRelationship]:
        account = await self._linked(user_id)
        try:
            live = await self.alpaca.list_ach_relationships(account.alpaca_account_id)
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        states = {str(v["id"]): str(v["status"]) for v in live}
        async with self.uow() as work:
            banks = await work.banks.list(user_id=user_id)
            for bank in banks:
                if bank.alpaca_relationship_id in states:
                    await work.banks.save(replace(bank, status=states[bank.alpaca_relationship_id]))
            return await work.banks.list(user_id=user_id)

    async def get_bank_relationship(self, user_id: UUID, bank_id: UUID) -> BankRelationship:
        async with self.uow() as work:
            bank = await work.banks.get(id=bank_id, user_id=user_id)
        if bank is None:
            raise not_found()
        return bank

    async def request_transfer(
        self,
        user_id: UUID,
        direction: Direction,
        bank_id: UUID,
        raw_amount: str,
        currency: str,
        key: str,
    ) -> Transfer:
        validate_currency(currency)
        amount = parse_transfer_amount(raw_amount, self.maximum)
        if direction not in {"INCOMING", "OUTGOING"}:
            raise invalid("direction")
        if not re.fullmatch(r"[\x20-\x7e]{8,128}", key):
            raise invalid("Idempotency-Key")
        digest, now = request_hash(direction, bank_id, amount, currency), self.clock.now()
        async with self.uow() as work:
            await work.lock_user(user_id)
            existing = await work.keys.get(user_id=user_id, idempotency_key=key)
            if existing:
                if existing.request_hash != digest or existing.state != "completed":
                    reason = "body_mismatch" if existing.request_hash != digest else "in_progress"
                    raise AppError(
                        409,
                        ErrorCode.IDEMPOTENCY_CONFLICT,
                        "Idempotency conflict.",
                        {"reason": reason},
                    )
                transfer = await work.transfers.get(id=existing.transfer_id, user_id=user_id)
                if transfer is None:
                    raise not_found()
                return transfer
            account = await work.accounts.get(user_id)
            if account is None or not account.is_active:
                raise AppError(409, ErrorCode.WALLET_ACCOUNT_NOT_ACTIVE, "Active account required.")
            bank = await work.banks.get(id=bank_id, user_id=user_id)
            if bank is None or bank.status != "APPROVED":
                raise AppError(
                    409, ErrorCode.BANK_RELATIONSHIP_NOT_USABLE, "Bank relationship is not usable."
                )
            entry = IdempotencyEntry(user_id, key, digest, "in_progress", None, now)
            if not await work.keys.insert(entry):
                raise AppError(409, ErrorCode.IDEMPOTENCY_CONFLICT, "Transfer in progress.")
        try:
            if direction == "OUTGOING":
                raw_balance = await self.alpaca.get_trading_account(
                    account.alpaca_account_id, timeout_s=5
                )
                try:
                    available = Decimal(raw_balance["cash_withdrawable"])
                    if not available.is_finite():
                        raise ValueError()
                except (InvalidOperation, ValueError, KeyError, TypeError):
                    raise AppError(
                        502, ErrorCode.ALPACA_UNAVAILABLE, "Withdrawable funds are unavailable."
                    ) from None
                check_withdrawable(amount, available)
            raw = await self.alpaca.create_transfer(
                account.alpaca_account_id, bank.alpaca_relationship_id, amount, direction
            )
        except AlpacaValidationError as exc:
            async with self.uow() as work:
                await work.keys.delete(user_id=user_id, idempotency_key=key)
            raise AppError(
                422,
                ErrorCode.TRANSFER_REJECTED,
                "Alpaca rejected the transfer.",
                {"reason": str(exc)[:300]},
            ) from None
        except AppError:
            # These errors occur before POST; the same key can safely be retried.
            async with self.uow() as work:
                await work.keys.delete(user_id=user_id, idempotency_key=key)
            raise
        except AlpacaError as exc:
            # Keep the reservation after an ambiguous provider failure: never retry POST blindly.
            raise to_app_error(exc) from None
        transfer = Transfer(
            uuid4(),
            user_id,
            account.alpaca_account_id,
            str(raw["id"]),
            bank_id,
            direction,
            amount,
            raw.get("currency") or "USD",
            str(raw["status"]),
            raw.get("reason"),
            raw.get("description"),
            timestamp(raw.get("updated_at")),
            now,
            timestamp(raw.get("created_at")) or now,
        )
        async with self.uow() as work:
            await work.transfers.insert(transfer)
            await work.keys.save(replace(entry, state="completed", transfer_id=transfer.id))
        return transfer

    async def get_transfer(self, user_id: UUID, transfer_id: UUID) -> Transfer:
        async with self.uow() as work:
            transfer = await work.transfers.get(id=transfer_id, user_id=user_id)
        if transfer is None:
            raise not_found()
        return transfer

    async def list_transfers(
        self,
        user_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
        direction: str | None = None,
        page_size: int = 50,
        cursor: str | None = None,
    ) -> Page[Transfer]:
        await self._linked(user_id)
        start, end = period(self.clock.now(), start, end)
        if direction is not None and direction not in {"INCOMING", "OUTGOING"}:
            raise invalid("direction")
        async with self.uow() as work:
            values = await work.transfers.list(user_id=user_id)
        return paginate(
            [
                v
                for v in values
                if start <= v.created_at <= end and (direction is None or v.direction == direction)
            ],
            page_size,
            cursor,
        )
