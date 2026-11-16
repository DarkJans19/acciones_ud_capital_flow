import base64
from uuid import UUID

from acciones_ud.brokers.domain.errors import ValidationError


def search_cursor(name: str, ident: UUID) -> str:
    return base64.urlsafe_b64encode(f"{name.lower()}|{ident}".encode()).decode()


def read_search_cursor(cursor: str) -> tuple[str, UUID]:
    try:
        raw = base64.b64decode(cursor.encode(), altchars=b"-_", validate=True).decode()
        name, ident = raw.rsplit("|", 1)
        if not name or len(name) > 1000:
            raise ValueError()
        return name, UUID(ident)
    except (ValueError, UnicodeError):
        raise ValidationError("cursor") from None
