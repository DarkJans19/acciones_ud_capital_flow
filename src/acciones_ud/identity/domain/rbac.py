from collections.abc import Iterable, Mapping
from datetime import datetime

from acciones_ud.identity.domain.models import RoleAssignment
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def effective_roles(
    assignments: Iterable[RoleAssignment],
    now: datetime,
    account_status: str = "active",
) -> frozenset[str]:
    if account_status != "active":
        return frozenset()
    return frozenset(
        a.role
        for a in assignments
        if a.status != "CANCELLED"
        and a.valid_from <= now
        and (a.valid_to is None or now < a.valid_to)
    )


def permissions_for(roles: Iterable[str], mapping: Mapping[str, set[str]]) -> frozenset[str]:
    return frozenset(p for role in roles for p in mapping.get(role, set()))


def validate_validity(valid_from: datetime, valid_to: datetime | None) -> None:
    if valid_from.utcoffset() is None:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: valid_from")
    if valid_to is not None and (valid_to.utcoffset() is None or valid_to <= valid_from):
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: valid_to")


def guard_last_administrator(
    before: Iterable[RoleAssignment],
    after: Iterable[RoleAssignment],
    now: datetime,
    active_users: set[object],
) -> None:
    def has_admin(assignments: Iterable[RoleAssignment]) -> bool:
        return any(
            a.user_id in active_users
            and a.role == "administrator"
            and a.status != "CANCELLED"
            and a.valid_from <= now
            and (a.valid_to is None or now < a.valid_to)
            for a in assignments
        )

    if has_admin(before) and not has_admin(after):
        raise AppError(409, ErrorCode.LAST_ADMINISTRATOR, "The last administrator is required.")
