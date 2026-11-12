"""Which Session a logout request revokes (DD15, Requirement 4 criteria 6, 11 and 12).

Pure decision, independent of persistence: the access token wins when it is valid
and its Session is still active; otherwise the refresh-token digest identifies the
Session; otherwise nothing is revoked.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from acciones_ud.identity.domain.models import AccessClaims

_REFRESH_SHAPE = re.compile(r"[A-Za-z0-9_-]{43}")


class LogoutChoice(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    NONE = "none"


@dataclass(frozen=True)
class LogoutTarget:
    choice: LogoutChoice
    user_id: UUID | None = None
    session_id: UUID | None = None


def is_refresh_cookie(value: str | None) -> bool:
    """The stored refresh token is 32 random bytes encoded as 43 URL-safe characters."""
    return value is not None and _REFRESH_SHAPE.fullmatch(value) is not None


def target(
    access: AccessClaims | None,
    access_session_active: bool,
    refresh_digest: bytes | None,
) -> LogoutTarget:
    if access is not None and access_session_active:
        return LogoutTarget(LogoutChoice.ACCESS, access.user_id, access.session_id)
    if refresh_digest is not None:
        return LogoutTarget(LogoutChoice.REFRESH)
    return LogoutTarget(LogoutChoice.NONE)
