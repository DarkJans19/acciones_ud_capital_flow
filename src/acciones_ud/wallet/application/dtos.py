import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from acciones_ud.shared.domain.errors import AppError, ErrorCode


def invalid(*fields: str) -> AppError:
    return AppError(
        422, ErrorCode.VALIDATION_ERROR, "Invalid request fields.", {"fields": list(fields)}
    )


def timestamp(value: str | int | float | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, (int, float)):
        result = datetime.fromtimestamp(value, UTC)
    else:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result


def period(
    now: datetime, start: datetime | None, end: datetime | None
) -> tuple[datetime, datetime]:
    end = end or now
    start = start or end - timedelta(days=30)
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or start > end
        or end - start > timedelta(days=366)
    ):
        raise invalid("from", "to")
    return start, end


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    next_cursor: str | None


def paginate[T](
    values: list[T], size: int, cursor: str | None, *, date_field: str = "created_at"
) -> Page[T]:
    if not 1 <= size <= 100:
        raise invalid("page_size")

    def key(value: Any) -> tuple[datetime, str]:
        at: datetime = getattr(value, date_field)
        return at, str(value.id)

    values = sorted(values, key=key, reverse=True)
    if cursor:
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
            date, ident = decoded.split("|", 1)
            at = datetime.fromisoformat(date)
            if not ident or at.tzinfo is None:
                raise ValueError()
        except (ValueError, UnicodeError):
            raise invalid("cursor") from None
        values = [value for value in values if key(value) < (at, ident)]
    selected = values[:size]
    next_cursor = (
        base64.urlsafe_b64encode(
            (key(selected[-1])[0].isoformat() + "|" + key(selected[-1])[1]).encode()
        ).decode()
        if (len(values) > size)
        else None
    )
    return Page(selected, next_cursor)
