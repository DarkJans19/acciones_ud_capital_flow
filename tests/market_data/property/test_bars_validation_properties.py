# Feature: identity-market-backend, Property 21: Bars request validation

from datetime import UTC, date, datetime, time

import pytest
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.bars import TIMEFRAMES, parse_instant, validate_bars_request
from acciones_ud.shared.domain.errors import AppError

VALID_INSTANTS = st.one_of(
    st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2100, 1, 1),
        timezones=st.just(UTC),
    ).map(lambda value: value.isoformat()),
    st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 1, 1)).map(
        lambda value: value.isoformat()
    ),
)


def _is_invalid(value: str) -> bool:
    try:
        parse_instant(value, end_of_day=False)
    except ValueError:
        return True
    return False


INVALID_INSTANTS = st.text(min_size=0, max_size=12).filter(_is_invalid)


def expected_errors(timeframe: str, start: str, end: str, page_size: int) -> set[str]:
    errors: set[str] = set()
    if timeframe not in TIMEFRAMES:
        errors.add("timeframe")
    try:
        start_at = parse_instant(start, end_of_day=False)
    except ValueError:
        start_at = None
        errors.add("start")
    try:
        end_at = parse_instant(end, end_of_day=True)
    except ValueError:
        end_at = None
        errors.add("end")
    if start_at is not None and end_at is not None and start_at > end_at:
        errors.add("start")
    if not 1 <= page_size <= 10000:
        errors.add("page_size")
    return errors


@given(
    timeframe=st.one_of(st.sampled_from(TIMEFRAMES), st.text(max_size=8)),
    start=st.one_of(VALID_INSTANTS, INVALID_INSTANTS),
    end=st.one_of(VALID_INSTANTS, INVALID_INSTANTS),
    page_size=st.one_of(
        st.integers(min_value=1, max_value=10000),
        st.integers(max_value=0),
        st.integers(min_value=10001),
    ),
)
def test_bars_validation_accepts_exactly_the_documented_domain(
    timeframe: str, start: str, end: str, page_size: int
) -> None:
    errors = expected_errors(timeframe, start, end, page_size)
    if not errors:
        start_at, end_at = validate_bars_request(timeframe, start, end, page_size)
        assert start_at <= end_at
        return
    with pytest.raises(AppError) as error:
        validate_bars_request(timeframe, start, end, page_size)
    assert error.value.status == 422
    reported = {item["field"] for item in (error.value.details or {}).get("errors", [])}
    assert reported == errors


def test_date_only_end_means_end_of_day_utc() -> None:
    start_at, end_at = validate_bars_request("1Day", "2026-01-02", "2026-01-03", 1000)
    assert start_at == datetime(2026, 1, 2, tzinfo=UTC)
    assert end_at == datetime.combine(date(2026, 1, 3), time.max, tzinfo=UTC)
