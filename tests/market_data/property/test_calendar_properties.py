# Feature: identity-market-backend, Property 26: Calendar expansion and schedule resolution

from datetime import date, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.calendar import expand
from acciones_ud.market_data.domain.entities import (
    CalendarSession,
    DayKind,
    Market,
    ScheduleOverride,
)
from acciones_ud.market_data.domain.schedule import resolve
from acciones_ud.shared.domain.errors import AppError

NEW_YORK = ZoneInfo("America/New_York")
TARGETS = st.sampled_from(
    [ZoneInfo("America/New_York"), ZoneInfo("UTC"), ZoneInfo("Europe/Madrid")]
)
START = date(2026, 1, 1)


def _time(hour: int, minute: int = 0) -> time:
    return time(hour=hour, minute=minute)


SESSIONS = st.lists(
    st.builds(
        CalendarSession,
        date=st.integers(min_value=0, max_value=40).map(lambda days: START + timedelta(days=days)),
        open_at=st.just(_time(9, 30)),
        close_at=st.just(_time(16)),
    ),
    max_size=12,
).map(lambda items: list({item.date: item for item in items}.values()))

def _override(payload: tuple[date, bool]) -> ScheduleOverride:
    day, closed = payload
    if closed:
        return ScheduleOverride(
            id=uuid4(),
            market_code="NYSE",
            date=day,
            closed=True,
            open_time=None,
            close_time=None,
        )
    return ScheduleOverride(
        id=uuid4(),
        market_code="NYSE",
        date=day,
        closed=False,
        open_time=_time(10),
        close_time=_time(15),
    )


OVERRIDES = st.lists(
    st.tuples(
        st.integers(min_value=0, max_value=40).map(lambda days: START + timedelta(days=days)),
        st.booleans(),
    ),
    max_size=12,
).map(lambda items: list({item[0]: _override(item) for item in items}.values()))

MARKETS = st.one_of(
    st.none(),
    st.builds(
        Market,
        code=st.just("NYSE"),
        name=st.just("New York Stock Exchange"),
        default_open_time=st.one_of(st.none(), st.just(_time(9, 30))),
        default_close_time=st.one_of(st.none(), st.just(_time(16))),
    ),
)


def expected_day(
    day: date,
    sessions: dict[date, CalendarSession],
    overrides: dict[date, ScheduleOverride],
    market: Market | None,
) -> tuple[DayKind, bool]:
    if day in overrides:
        override = overrides[day]
        if override.closed:
            kind = DayKind.WEEKEND if day.weekday() >= 5 else DayKind.HOLIDAY
            return kind, True
        return DayKind.TRADING_DAY, True
    if day in sessions:
        return DayKind.TRADING_DAY, False
    return (DayKind.WEEKEND if day.weekday() >= 5 else DayKind.HOLIDAY), False


@given(sessions=SESSIONS, overrides=OVERRIDES, market=MARKETS, target=TARGETS)
def test_calendar_expansion_and_resolution(
    sessions: list[CalendarSession],
    overrides: list[ScheduleOverride],
    market: Market | None,
    target: ZoneInfo,
) -> None:
    start = START
    end = start + timedelta(days=30)
    days = expand(start, end, sessions, overrides, market, target)

    assert len(days) == 31
    assert [day.date for day in days] == [start + timedelta(days=offset) for offset in range(31)]
    session_by_day = {session.date: session for session in sessions}
    override_by_day = {override.date: override for override in overrides}

    for entry in days:
        kind, is_override = expected_day(
            entry.date, session_by_day, override_by_day, market
        )
        assert entry.kind is kind
        assert entry.override is is_override
        if kind is DayKind.TRADING_DAY:
            assert entry.open_at is not None and entry.close_at is not None
            assert entry.open_at.tzinfo is not None
        else:
            assert entry.open_at is None and entry.close_at is None


def test_status_equals_the_calendar_entry() -> None:
    day = date(2026, 1, 5)
    market = Market(code="NYSE", name="New York Stock Exchange")
    session = CalendarSession(date=day, open_at=time(9, 30), close_at=time(16))
    entry = resolve(day, session, None, market, NEW_YORK)
    days = expand(day, day, [session], [], market, NEW_YORK)
    assert days == [entry]


def test_range_longer_than_366_days_is_rejected() -> None:
    from pytest import raises

    with raises(AppError):
        expand(date(2026, 1, 1), date(2027, 1, 2), [], [], None, NEW_YORK)
