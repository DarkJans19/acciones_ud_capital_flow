from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from acciones_ud.admin.domain.errors import invalid
from acciones_ud.admin.domain.model import FeeVersion, Raw
from acciones_ud.shared.domain.trading import CommissionTerms

SEED_ID = UUID("00000000-0000-0000-0000-000000000701")
SEED_TERMS = CommissionTerms(SEED_ID, Decimal("2.0000"), Decimal("60.00"))


def validate_new_version(rate: Decimal, share: Decimal, at: datetime, now: datetime) -> None:
    for value, maximum, scale, name in (
        (rate, Decimal(10), 4, "commission_rate_pct"),
        (share, Decimal(100), 2, "platform_share_pct"),
    ):
        exponent = value.as_tuple().exponent
        if (
            not value.is_finite()
            or not 0 <= value <= maximum
            or not isinstance(exponent, int)
            or exponent < -scale
        ):
            raise invalid(name)
    if at.utcoffset() is None:
        raise invalid("effective_from", "timezone_required")
    if at < now:
        raise invalid("effective_from", "retroactive")


def resolve_terms(versions: Iterable[FeeVersion], market: str, at: datetime) -> CommissionTerms:
    rows = [v for v in versions if v.canceled_at is None and v.effective_from <= at]
    for scope in (market, "default"):
        candidates = [v for v in rows if v.scope == scope]
        if candidates:
            return max(candidates, key=lambda v: (v.effective_from, v.version_no)).terms
    # A missing seed is a schema fault, never silently a reference commission.
    raise RuntimeError("No effective default fee version")


def version_status(version: FeeVersion, versions: Iterable[FeeVersion], at: datetime) -> str:
    if version.canceled_at is not None:
        return "canceled"
    if version.effective_from > at:
        return "scheduled"
    return (
        "in_force"
        if resolve_terms(versions, version.scope, at).fee_version_id == version.id
        else "superseded"
    )


def can_cancel(version: FeeVersion, at: datetime) -> bool:
    return version.canceled_at is None and version.effective_from > at


def matrix(versions: list[FeeVersion], markets: list[str], at: datetime) -> list[Raw]:
    return [
        {
            "scope": scope,
            "terms": resolve_terms(versions, scope, at),
            "origin": "market"
            if any(
                v.market_code == scope and v.effective_from <= at and v.canceled_at is None
                for v in versions
            )
            else "default",
            "scheduled": [
                v
                for v in versions
                if v.scope == scope and v.canceled_at is None and v.effective_from > at
            ],
        }
        for scope in ["default", *markets]
    ]
