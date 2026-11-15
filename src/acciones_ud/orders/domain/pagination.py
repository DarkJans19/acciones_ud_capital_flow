import base64
from datetime import datetime
from uuid import UUID

from acciones_ud.shared.domain.errors import AppError, ErrorCode


def encode(at: datetime, ident: UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{ident}".encode()).decode()


def decode(cursor: str) -> tuple[datetime, UUID]:
    try:
        at, ident = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        instant = datetime.fromisoformat(at)
        if instant.tzinfo is None:
            raise ValueError()
        return instant, UUID(ident)
    except (ValueError, UnicodeError):
        raise AppError(
            422, ErrorCode.VALIDATION_ERROR, "Invalid field: cursor", {"fields": ["cursor"]}
        ) from None
