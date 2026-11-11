"""RF-25 / Properties 20 and 21: bars validation and mapping."""

from datetime import UTC, date, datetime, time

from acciones_ud.market_data.domain.entities import Bar, BarsPage
from acciones_ud.shared.domain.errors import AppError, ErrorCode

TIMEFRAMES = ("1Min", "5Min", "15Min", "1Hour", "1Day")
DEFAULT_PAGE_SIZE = 1000
MAX_PAGE_SIZE = 10000


def parse_instant(value: str, *, end_of_day: bool) -> datetime:
    raw = value.strip()
    if "T" not in raw and " " not in raw:
        parsed_date = date.fromisoformat(raw)
        moment = time.max if end_of_day else time.min
        return datetime.combine(parsed_date, moment, tzinfo=UTC)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def validate_bars_request(
    timeframe: str,
    start: str,
    end: str,
    page_size: int,
) -> tuple[datetime, datetime]:
    errors: list[dict[str, str]] = []
    if timeframe not in TIMEFRAMES:
        errors.append({"field": "timeframe", "issue": "unsupported timeframe"})
    try:
        start_at = parse_instant(start, end_of_day=False)
    except ValueError:
        start_at = None
        errors.append({"field": "start", "issue": "invalid timestamp"})
    try:
        end_at = parse_instant(end, end_of_day=True)
    except ValueError:
        end_at = None
        errors.append({"field": "end", "issue": "invalid timestamp"})
    if start_at is not None and end_at is not None and start_at > end_at:
        errors.append({"field": "start", "issue": "start is later than end"})
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        errors.append({"field": "page_size", "issue": "out of range"})
    if errors:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid field: {errors[0]['field']}",
            {"errors": errors},
        )
    assert start_at is not None and end_at is not None
    return start_at, end_at


def map_bars(
    bars: list[Bar],
    start: datetime,
    end: datetime,
    page_size: int,
    next_page_token: str | None = None,
) -> BarsPage:
    inside = [bar for bar in bars if start <= bar.timestamp <= end]
    inside.sort(key=lambda bar: bar.timestamp)
    return BarsPage(bars=inside[:page_size], next_page_token=next_page_token)
