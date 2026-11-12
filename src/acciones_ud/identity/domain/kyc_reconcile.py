"""Pure KYC reconciliation rules (DD18, Requirement 24)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from acciones_ud.identity.domain.kyc import AlpacaAccountSummary
from acciones_ud.shared.domain.alpaca_errors import (
    AlpacaError,
    AlpacaNotFound,
    AlpacaRateLimited,
    AlpacaUnavailable,
)
from acciones_ud.shared.domain.errors import AppError, ErrorCode

RESERVATION_GRACE_SECONDS = 120


class ReconcileDecision(StrEnum):
    ALREADY_LINKED = "already_linked"
    LOOKUP_BY_ID = "lookup_by_id"
    SEARCH_BY_EMAIL = "search_by_email"


@dataclass(frozen=True)
class KycState:
    link: str
    alpaca_account_id: str | None = None
    status: str | None = None
    reserved_at: datetime | None = None


@dataclass(frozen=True)
class Found:
    account: AlpacaAccountSummary


@dataclass(frozen=True)
class NotFound:
    pass


@dataclass(frozen=True)
class Ambiguous:
    count: int


def precheck(state: KycState, supplied: UUID | None, now: datetime) -> ReconcileDecision:
    """Decision table of 24.5, 24.6 and 24.8; conflicts raise their AppError."""
    if state.link == "linked":
        stored = UUID(state.alpaca_account_id) if state.alpaca_account_id else None
        if supplied is None or (stored is not None and supplied == stored):
            return ReconcileDecision.ALREADY_LINKED
        raise AppError(
            409, ErrorCode.KYC_ACCOUNT_EXISTS, "The user already has another Alpaca account."
        )
    if (
        state.link == "unlinked"
        and state.reserved_at is not None
        and (now - state.reserved_at).total_seconds() < RESERVATION_GRACE_SECONDS
    ):
        raise AppError(
            409, ErrorCode.KYC_SUBMISSION_IN_PROGRESS, "A KYC submission is in progress."
        )
    return (
        ReconcileDecision.LOOKUP_BY_ID
        if supplied is not None
        else ReconcileDecision.SEARCH_BY_EMAIL
    )


def pick_candidate(
    accounts: list[AlpacaAccountSummary], registered_email: str
) -> Found | NotFound | Ambiguous:
    target = registered_email.strip().casefold()
    matched = [
        account
        for account in accounts
        if (account.contact_email or "").strip().casefold() == target
    ]
    if not matched:
        return NotFound()
    if len(matched) > 1:
        return Ambiguous(len(matched))
    return Found(matched[0])


def reconcile_alpaca_error(exc: AlpacaError) -> AppError:
    """Reconciliation never maps a 404 to SYMBOL_NOT_FOUND (24.3)."""
    if isinstance(exc, AlpacaNotFound):
        return AppError(
            404, ErrorCode.KYC_RECONCILE_NOT_FOUND, "Alpaca account not found."
        )
    if isinstance(exc, AlpacaRateLimited):
        return AppError(503, ErrorCode.ALPACA_RATE_LIMITED, "Alpaca rate limit reached.")
    if isinstance(exc, AlpacaUnavailable):
        return AppError(502, ErrorCode.ALPACA_UNAVAILABLE, "Alpaca is unavailable.")
    return AppError(500, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred.")
