from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AssignmentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class RoleAssignment:
    id: UUID
    user_id: UUID
    role: str
    valid_from: datetime
    valid_to: datetime | None = None
    status: AssignmentStatus = AssignmentStatus.ACTIVE


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    session_id: UUID
    email: str
    account_status: str
    is_premium: bool
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class AccessClaims:
    user_id: UUID
    session_id: UUID
    issued_at: datetime
    expires_at: datetime
