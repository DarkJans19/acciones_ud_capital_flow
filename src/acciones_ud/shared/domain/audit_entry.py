"""RF-44: shared allowlisted audit envelope, independent of persistence."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class RequestMeta:
    ip_address: str | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class AuditRecord:
    id: UUID
    actor_user_id: UUID
    action: str
    target_type: str
    target_id: str
    payload: dict[str, Any]
    occurred_at: datetime
    ip_address: str | None = None
    request_id: str | None = None


def build_record(
    action: str,
    keys: frozenset[str],
    actor: UUID,
    target_type: str,
    target_id: str,
    payload: dict[str, Any],
    at: datetime,
    meta: RequestMeta | None = None,
) -> AuditRecord:
    if payload.keys() != keys:
        raise ValueError("Audit payload does not match its allowlist")
    meta = meta or RequestMeta()
    return AuditRecord(
        uuid4(),
        actor,
        action,
        target_type,
        target_id,
        payload,
        at,
        meta.ip_address,
        meta.request_id,
    )
