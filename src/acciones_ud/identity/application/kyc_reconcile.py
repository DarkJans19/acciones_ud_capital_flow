"""Administrative KYC reconciliation use case (Requirement 24, D9)."""

from uuid import UUID

from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.kyc import AlpacaAccountSummary
from acciones_ud.identity.domain.kyc_ports import AlpacaAccountsPort, KycWorkFactory
from acciones_ud.identity.domain.kyc_reconcile import (
    Ambiguous,
    KycState,
    NotFound,
    ReconcileDecision,
    pick_candidate,
    precheck,
    reconcile_alpaca_error,
)
from acciones_ud.shared.domain.alpaca_errors import AlpacaError
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def _state(row: Record | None) -> KycState:
    if row is None:
        return KycState("none")
    if row.get("alpaca_account_id") is None:
        return KycState("unlinked", reserved_at=row["reserved_at"])
    return KycState("linked", row["alpaca_account_id"], row.get("status"))


class KycReconcileService:
    def __init__(self, uow: KycWorkFactory, accounts: AlpacaAccountsPort, clock: Clock) -> None:
        self.uow, self.accounts, self.clock = uow, accounts, clock

    async def reconcile(
        self, actor_id: UUID | None, user_id: UUID, alpaca_account_id: UUID | None
    ) -> Record:
        now = self.clock.now()
        # Unit of work 1: short read; no transaction is held during the Alpaca call.
        async with self.uow() as work:
            email = await work.kyc.user_email(user_id)
            row = await work.kyc.get(user_id)
        state = _state(row)
        decision = precheck(state, alpaca_account_id, now)
        if decision is ReconcileDecision.ALREADY_LINKED:
            return self._out(state.alpaca_account_id, state.status, user_id, "already_linked")

        candidate = (
            await self._by_id(str(alpaca_account_id))
            if decision is ReconcileDecision.LOOKUP_BY_ID and alpaca_account_id is not None
            else await self._by_email(email)
        )

        # Unit of work 2: conditional write, never overwriting a stored identifier.
        async with self.uow() as work:
            owner = await work.kyc.get_by_alpaca_id(candidate.id)
            if owner is not None and owner["user_id"] != user_id:
                raise self._in_use()
            if state.link == "none":
                linked = await work.kyc.link_new(
                    user_id, candidate.id, candidate.status, now
                )
            else:
                assert state.reserved_at is not None
                linked = await work.kyc.link_reserved(
                    user_id, candidate.id, candidate.status, now, state.reserved_at
                )
            if not linked:
                owner = await work.kyc.get_by_alpaca_id(candidate.id)
                if owner is not None and owner["user_id"] != user_id:
                    raise self._in_use()
                fresh = _state(await work.kyc.get(user_id))
                again = precheck(fresh, UUID(candidate.id), now)
                if again is ReconcileDecision.ALREADY_LINKED:
                    return self._out(
                        fresh.alpaca_account_id, fresh.status, user_id, "already_linked"
                    )
                raise AppError(
                    409,
                    ErrorCode.KYC_SUBMISSION_IN_PROGRESS,
                    "A KYC submission is in progress.",
                )
        return self._out(candidate.id, candidate.status, user_id, "linked")

    async def _by_id(self, account_id: str) -> AlpacaAccountSummary:
        try:
            account = await self.accounts.get_account(account_id)
        except AlpacaError as exc:
            raise reconcile_alpaca_error(exc) from None
        return AlpacaAccountSummary(account.id, account.status, account.updated_at)

    async def _by_email(self, email: str) -> AlpacaAccountSummary:
        try:
            accounts = await self.accounts.list_accounts(email)
        except AlpacaError as exc:
            raise reconcile_alpaca_error(exc) from None
        picked = pick_candidate(accounts, email)
        if isinstance(picked, NotFound):
            raise AppError(
                404,
                ErrorCode.KYC_RECONCILE_NOT_FOUND,
                "No Alpaca account matches the registered email.",
            )
        if isinstance(picked, Ambiguous):
            raise AppError(
                409,
                ErrorCode.KYC_RECONCILE_AMBIGUOUS,
                "Several Alpaca accounts match; supply an alpaca_account_id.",
                {"count": picked.count},
            )
        return picked.account

    @staticmethod
    def _in_use() -> AppError:
        return AppError(
            409,
            ErrorCode.ALPACA_ACCOUNT_IN_USE,
            "Alpaca account already linked to another user.",
        )

    @staticmethod
    def _out(
        alpaca_account_id: str | None,
        status: str | None,
        user_id: UUID,
        outcome: str,
    ) -> Record:
        return {
            "user_id": user_id,
            "alpaca_account_id": alpaca_account_id,
            "status": status,
            "outcome": outcome,
        }
