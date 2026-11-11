from dataclasses import replace
from datetime import date
from uuid import UUID

from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.kyc import can_trade
from acciones_ud.identity.domain.kyc_ports import AlpacaAccountsPort, KycWorkFactory
from acciones_ud.identity.domain.kyc_submission import AccountOpeningRequest
from acciones_ud.identity.domain.redaction import last4, redact
from acciones_ud.shared.domain.alpaca_errors import AlpacaError, AlpacaValidationError, to_app_error
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class KycService:
    def __init__(self, uow: KycWorkFactory, accounts: AlpacaAccountsPort, clock: Clock) -> None:
        self.uow, self.accounts, self.clock = uow, accounts, clock

    async def submit(self, user_id: UUID, request: AccountOpeningRequest) -> Record:
        now = self.clock.now()
        request = replace(request, signed_at=now)
        try:
            birthday = date.fromisoformat(str(request.identity.get("date_of_birth", "")))
        except ValueError:
            raise AppError(
                422, ErrorCode.VALIDATION_ERROR, "Invalid field: date_of_birth"
            ) from None
        if birthday >= now.date():
            raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: date_of_birth")
        if request.agreements.get("customer_agreement") is not True:
            raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: customer_agreement")
        async with self.uow() as work:
            reserved = await work.kyc.reserve(user_id, now)
        if not reserved:
            raise AppError(
                409, ErrorCode.KYC_ACCOUNT_EXISTS, "KYC account exists or is being opened."
            )
        tax_id = str(request.identity["tax_id"])
        try:
            account = await self.accounts.create_account(request)
        except AlpacaError as exc:
            async with self.uow() as work:
                await work.kyc.release(user_id, now)
            if isinstance(exc, AlpacaValidationError):
                raise AppError(422, ErrorCode.ALPACA_REJECTED, redact(str(exc), tax_id)) from None
            raise to_app_error(exc) from None
        async with self.uow() as work:
            stored = await work.kyc.complete(user_id, now, account, last4(tax_id))
        if not stored:
            # Do not delete another request's reservation or retry an external account creation.
            raise AppError(
                503, ErrorCode.DATABASE_UNAVAILABLE, "KYC completion requires reconciliation."
            )
        return {"alpaca_account_id": account.id, "status": account.status}

    async def status(self, user_id: UUID) -> Record:
        async with self.uow() as work:
            stored = await work.kyc.get(user_id)
        if not stored or not stored["alpaca_account_id"]:
            return {
                "has_account": False,
                "status": None,
                "status_updated_at": None,
                "can_trade": False,
                "stale": False,
            }
        status, updated = stored["status"], stored["status_updated_at"]
        stale = False
        try:
            live = await self.accounts.get_account(stored["alpaca_account_id"])
            if live.status != status:
                async with self.uow() as work:
                    await work.kyc.update_status(user_id, live)
                status, updated = live.status, live.updated_at or self.clock.now()
        except AlpacaError:
            stale = True
        return {
            "has_account": True,
            "status": status,
            "status_updated_at": updated,
            "can_trade": can_trade(status),
            "stale": stale,
        }
