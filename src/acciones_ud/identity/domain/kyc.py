from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from acciones_ud.shared.domain.errors import AppError, ErrorCode


@dataclass(frozen=True)
class AlpacaAccount:
    id: str
    status: str
    updated_at: datetime | None = None


@dataclass(frozen=True)
class AlpacaAccountSummary:
    id: str
    status: str
    updated_at: datetime | None = None
    contact_email: str | None = None


def can_trade(status: str | None) -> bool:
    return status == "ACTIVE"


def reservation_stale(reserved_at: datetime, now: datetime) -> bool:
    return now - reserved_at > timedelta(seconds=120)


def financial_range(label: str, approved: Mapping[str, tuple[Decimal, Decimal]]) -> tuple[str, str]:
    """No product ranges are assumed: only an explicitly approved mapping is accepted."""
    if label not in approved:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Unknown financial range.")
    low, high = approved[label]
    if not low.is_finite() or not high.is_finite() or low < 0 or high < low:
        raise ValueError("Invalid approved financial range")
    return str(low), str(high)
