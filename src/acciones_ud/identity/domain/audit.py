"""Audit_Log domain rules (Requirement 25, D11).

The payload whitelist is the only way into an entry, so a secret can reach the log
only by adding its key here.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class AuditAction(StrEnum):
    ADMINISTRATOR_CREATED = "administrator_created"
    BROKER_ACTIVATED = "broker_activated"
    PREMIUM_CHANGED = "premium_changed"
    ROLE_ASSIGNMENT_CREATED = "role_assignment_created"
    ROLE_ASSIGNMENT_UPDATED = "role_assignment_updated"
    ROLE_ASSIGNMENT_REVOKED = "role_assignment_revoked"
    ROLE_ASSIGNMENT_CANCELLED = "role_assignment_cancelled"
    ROLE_PERMISSION_ADDED = "role_permission_added"
    ROLE_PERMISSION_REMOVED = "role_permission_removed"
    KYC_RECONCILED = "kyc_reconciled"


PAYLOAD_KEYS: dict[AuditAction, frozenset[str]] = {
    AuditAction.ADMINISTRATOR_CREATED: frozenset(),
    AuditAction.BROKER_ACTIVATED: frozenset(
        {"broker_assignment_id", "investor_assignment_id"}
    ),
    AuditAction.PREMIUM_CHANGED: frozenset({"is_premium"}),
    AuditAction.ROLE_ASSIGNMENT_CREATED: frozenset(
        {"assignment_id", "role", "valid_from", "valid_to"}
    ),
    AuditAction.ROLE_ASSIGNMENT_UPDATED: frozenset(
        {
            "assignment_id",
            "role",
            "previous_valid_from",
            "previous_valid_to",
            "valid_from",
            "valid_to",
        }
    ),
    AuditAction.ROLE_ASSIGNMENT_REVOKED: frozenset({"assignment_id", "role"}),
    AuditAction.ROLE_ASSIGNMENT_CANCELLED: frozenset({"assignment_id", "role"}),
    AuditAction.ROLE_PERMISSION_ADDED: frozenset({"permission_code"}),
    AuditAction.ROLE_PERMISSION_REMOVED: frozenset({"permission_code"}),
    AuditAction.KYC_RECONCILED: frozenset({"alpaca_account_id", "outcome"}),
}


@dataclass(frozen=True)
class AuditEntry:
    id: UUID
    actor_user_id: UUID
    action: AuditAction
    target_type: str
    target_id: str
    payload: dict[str, Any]
    occurred_at: datetime


@dataclass(frozen=True)
class AuditQuery:
    action: AuditAction | None = None
    actor_user_id: UUID | None = None
    target_type: str | None = None
    target_id: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class AuditPage:
    items: tuple[AuditEntry, ...]
    total: int


def _json(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_entry(
    action: AuditAction,
    actor: UUID,
    target_type: str,
    target_id: str,
    payload: dict[str, Any],
    occurred_at: datetime,
    *,
    entry_id: UUID | None = None,
) -> AuditEntry:
    """Reject any missing or extra payload key (25.1, 25.6)."""
    expected = PAYLOAD_KEYS[action]
    if set(payload) != expected:
        raise ValueError(
            f"Invalid payload keys for {action}: expected {sorted(expected)}"
        )
    return AuditEntry(
        id=entry_id or uuid4(),
        actor_user_id=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload={key: _json(value) for key, value in payload.items()},
        occurred_at=occurred_at,
    )


def select(entries: list[AuditEntry], query: AuditQuery) -> AuditPage:
    """Executable specification of 25.7 to 25.9; the SQL repository mirrors it."""
    matched = [
        entry
        for entry in entries
        if (query.action is None or entry.action == query.action)
        and (query.actor_user_id is None or entry.actor_user_id == query.actor_user_id)
        and (query.target_type is None or entry.target_type == query.target_type)
        and (query.target_id is None or entry.target_id == query.target_id)
    ]
    ordered = sorted(matched, key=lambda entry: str(entry.id), reverse=True)
    ordered.sort(key=lambda entry: entry.occurred_at, reverse=True)
    page = ordered[query.offset : query.offset + query.limit]
    return AuditPage(items=tuple(page), total=len(ordered))
