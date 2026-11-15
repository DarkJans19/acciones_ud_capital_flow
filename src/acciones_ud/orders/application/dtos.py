from datetime import UTC, datetime


def instant(raw: str) -> datetime:
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
