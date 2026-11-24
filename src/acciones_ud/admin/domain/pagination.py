import base64
import json
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from acciones_ud.admin.domain.errors import invalid
from acciones_ud.admin.domain.model import Page


def encode(key: Sequence[str]) -> str:
    return base64.urlsafe_b64encode(json.dumps(list(key), separators=(",", ":")).encode()).decode()


def decode(token: str, length: int) -> tuple[str, ...]:
    try:
        if len(token) > 4096:
            raise ValueError()
        value = json.loads(base64.b64decode(token, altchars=b"-_", validate=True))
        if not isinstance(value, list) or len(value) != length:
            raise ValueError()
        if not all(isinstance(v, str) and 0 < len(v) <= 256 for v in value):
            raise ValueError()
        if value[0].isdigit() and len(value[0]) == 20:
            if int(value[0]) < 1:
                raise ValueError()
        elif datetime.fromisoformat(value[0]).utcoffset() is None:
            raise ValueError()
        if length == 3 and value[1] not in {"admin", "orders", "brokers", "auth"}:
            raise ValueError()
        return tuple(value)
    except (ValueError, UnicodeError, TypeError):
        raise invalid("cursor") from None


def paginate[T](
    rows: Sequence[T],
    key: Callable[[T], tuple[str, ...]],
    cursor: str | None,
    size: int,
) -> Page[T]:
    if not 1 <= size <= 100:
        raise invalid("page_size")
    values = sorted(rows, key=key, reverse=True)
    if cursor:
        boundary = decode(cursor, len(key(values[0])) if values else 2)
        values = [row for row in values if key(row) < boundary]
    selected = values[:size]
    return Page(selected, encode(key(selected[-1])) if len(values) > size else None)


def json_key(row: dict[str, Any]) -> tuple[str, ...]:
    return str(row["occurred_at"]), str(row["source"]), str(row["event_id"])
