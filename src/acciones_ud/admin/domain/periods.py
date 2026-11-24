from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from acciones_ud.admin.domain.errors import invalid


@dataclass(frozen=True)
class Period:
    from_: date
    to: date

    def __post_init__(self) -> None:
        if self.from_ > self.to or (self.to - self.from_).days >= 366 or self.to == date.max:
            raise invalid("period")

    def bounds(self) -> tuple[datetime, datetime]:
        zone = ZoneInfo("America/New_York")
        return (
            datetime.combine(self.from_, time.min, zone).astimezone(UTC),
            datetime.combine(self.to + timedelta(days=1), time.min, zone).astimezone(UTC),
        )
