from datetime import UTC, datetime, timedelta


class FakeClock:
    def __init__(self, instant: datetime | None = None) -> None:
        self.set(instant or datetime(2026, 1, 1, tzinfo=UTC))

    def set(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("Clock requires aware UTC time")
        self.instant = instant.astimezone(UTC)

    def now(self) -> datetime:
        return self.instant

    def advance(self, seconds: float) -> None:
        self.instant += timedelta(seconds=seconds)
