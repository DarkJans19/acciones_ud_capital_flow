"""Pure KYC status cache rules (DD16, Requirement 23).

The stored ``status_checked_at`` is both the cache timestamp and the guard that
keeps concurrent writers (job, ``/kyc/status`` and ``/users/me``) from moving the
status check backwards.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from acciones_ud.identity.domain.kyc import AlpacaAccount


@dataclass(frozen=True)
class KycStatusState:
    status: str | None
    status_updated_at: datetime | None
    checked_at: datetime | None


class CycleAction(StrEnum):
    STORE = "store"
    SKIP = "skip"
    END_CYCLE = "end_cycle"


def serve_cached(checked_at: datetime | None, now: datetime, ttl_seconds: int) -> bool:
    """True only when the stored check is fresh enough to answer without Alpaca (23.4, 23.6)."""
    if ttl_seconds <= 0 or checked_at is None:
        return False
    # A checked_at later than now (clock skew between instances) counts as fresh.
    return (now - checked_at).total_seconds() <= ttl_seconds


def apply_status_check(
    stored: KycStatusState, retrieved: AlpacaAccount, retrieved_at: datetime
) -> KycStatusState | None:
    """New state, or None when a later check is already stored (23.5, 23.10)."""
    if stored.checked_at is not None and stored.checked_at > retrieved_at:
        return None
    if retrieved.status == stored.status:
        return KycStatusState(stored.status, stored.status_updated_at, retrieved_at)
    return KycStatusState(
        retrieved.status, retrieved.updated_at or retrieved_at, retrieved_at
    )


def cycle_action(outcome: str) -> CycleAction:
    """Per-account outcome of one refresh cycle (23.7, 23.8)."""
    if outcome == "rate_limited":
        return CycleAction.END_CYCLE
    if outcome == "error":
        return CycleAction.SKIP
    return CycleAction.STORE
