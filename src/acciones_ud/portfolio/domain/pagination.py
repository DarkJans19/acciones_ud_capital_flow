import base64
import binascii
from datetime import datetime

from acciones_ud.shared.domain.errors import AppError, ErrorCode


def invalid(field: str) -> AppError:
    return AppError(422, ErrorCode.VALIDATION_ERROR, f"Invalid field: {field}", {"fields": [field]})


def validate_size(size: int) -> None:
    if not 1 <= size <= 100:
        raise invalid("page_size")


def encode(at: datetime, ident: str) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{ident}".encode()).decode()


def decode(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.b64decode(cursor.encode(), altchars=b"-_", validate=True).decode()
        at, ident = raw.split("|", 1)
        instant = datetime.fromisoformat(at)
        if instant.tzinfo is None or not ident or len(ident) > 256:
            raise ValueError()
        return instant, ident
    except (ValueError, UnicodeError, binascii.Error):
        raise invalid("cursor") from None
