"""Pure directory rules: filtering, ordering, paging and KYC field derivation.

Requirements 20 and 21 (decision D7). ``select`` is the executable specification
that the in-memory repository uses and that the SQL repository mirrors.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

Record = dict[str, Any]

KYC_STATUSES = (
    "INACTIVE",
    "ONBOARDING",
    "SUBMITTED",
    "SUBMISSION_FAILED",
    "ACTION_REQUIRED",
    "ACCOUNT_UPDATED",
    "APPROVAL_PENDING",
    "APPROVED",
    "REJECTED",
    "ACTIVE",
    "ACCOUNT_CLOSED",
)


@dataclass(frozen=True)
class DirectoryQuery:
    account_status: str | None = None
    role: str | None = None
    q: str | None = None
    broker_requested: bool | None = None
    kyc_status: str | None = None
    kyc_link_state: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class DirectoryEntry:
    user_id: UUID
    email: str
    first_names: str
    last_names: str
    phone: str | None
    country: str | None
    account_status: str
    is_premium: bool
    roles: tuple[str, ...]
    broker_requested: bool
    registered_at: datetime
    kyc_link_state: str
    kyc_alpaca_account_id: str | None = None
    kyc_status: str | None = None
    kyc_status_updated_at: datetime | None = None
    kyc_status_checked_at: datetime | None = None
    kyc_reserved_at: datetime | None = None
    kyc_created_at: datetime | None = None


@dataclass(frozen=True)
class DirectoryPage:
    items: tuple[DirectoryEntry, ...]
    total: int


def kyc_fields(kyc: Record | None) -> Record:
    """Derive KYC_Link_State and the nulls of 21.2 and 21.3 from the stored row."""
    if kyc is None:
        return {
            "kyc_link_state": "none",
            "kyc_alpaca_account_id": None,
            "kyc_status": None,
            "kyc_status_updated_at": None,
            "kyc_status_checked_at": None,
            "kyc_reserved_at": None,
            "kyc_created_at": None,
        }
    unlinked = kyc.get("alpaca_account_id") is None
    return {
        "kyc_link_state": "unlinked" if unlinked else "linked",
        "kyc_alpaca_account_id": None if unlinked else kyc["alpaca_account_id"],
        "kyc_status": None if unlinked else kyc["status"],
        "kyc_status_updated_at": None if unlinked else kyc["status_updated_at"],
        "kyc_status_checked_at": None if unlinked else kyc["status_checked_at"],
        "kyc_reserved_at": kyc["reserved_at"],
        "kyc_created_at": kyc["created_at"],
    }


def like_pattern(q: str) -> str:
    """Escape ``\\``, ``%`` and ``_`` so ``q`` matches literally (20.8)."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def effective_roles(row: Record, now: datetime) -> tuple[str, ...]:
    if row["account_status"] != "active":
        return ()
    names = {
        assignment["role_code"]
        for assignment in row.get("roles", ())
        if assignment.get("status", "ACTIVE") == "ACTIVE"
        and assignment["valid_from"] <= now
        and (assignment["valid_to"] is None or now < assignment["valid_to"])
    }
    return tuple(sorted(names))


def _entry(row: Record, roles: tuple[str, ...]) -> DirectoryEntry:
    return DirectoryEntry(
        user_id=row["id"],
        email=row["email"],
        first_names=row["first_names"],
        last_names=row["last_names"],
        phone=row.get("phone"),
        country=row.get("country"),
        account_status=row["account_status"],
        is_premium=bool(row["is_premium"]),
        roles=roles,
        broker_requested=bool(row["broker_requested"]),
        registered_at=row["created_at"],
        **kyc_fields(row.get("kyc")),
    )


def _matches(row: Record, roles: tuple[str, ...], query: DirectoryQuery) -> bool:
    if query.account_status is not None and row["account_status"] != query.account_status:
        return False
    if query.role is not None and query.role not in roles:
        return False
    if query.q is not None:
        needle = query.q.casefold()
        if not any(
            needle in (row.get(key) or "").casefold()
            for key in ("email", "first_names", "last_names")
        ):
            return False
    if query.broker_requested is not None and bool(row["broker_requested"]) != (
        query.broker_requested
    ):
        return False
    kyc = row.get("kyc")
    if query.kyc_status is not None and (
        kyc is None
        or kyc.get("alpaca_account_id") is None
        or kyc.get("status") != query.kyc_status
    ):
        return False
    if query.kyc_link_state is not None:
        if kyc_fields(kyc)["kyc_link_state"] != query.kyc_link_state:
            return False
    return True


def select(users: list[Record], query: DirectoryQuery, now: datetime) -> DirectoryPage:
    matched = []
    for row in users:
        roles = effective_roles(row, now)
        if _matches(row, roles, query):
            matched.append((row, roles))
    # Stable sort: identifier ascending first, then registration descending (20.1).
    ordered = sorted(matched, key=lambda pair: str(pair[0]["id"]))
    ordered.sort(key=lambda pair: pair[0]["created_at"], reverse=True)
    page = ordered[query.offset : query.offset + query.limit]
    return DirectoryPage(
        items=tuple(_entry(row, roles) for row, roles in page),
        total=len(ordered),
    )
