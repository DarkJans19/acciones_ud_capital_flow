# Feature: identity-market-backend, Property 27: Time zone conversion preserves the instant

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, available_timezones

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.timezones import iso, market_instant, zone
from acciones_ud.shared.domain.errors import AppError

ZONES = st.sampled_from(sorted(available_timezones()))
INSTANTS = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1), timezones=st.just(UTC)
)


@given(INSTANTS, ZONES)
def test_conversion_preserves_the_instant(instant: datetime, name: str) -> None:
    target = ZoneInfo(name)
    converted = datetime.fromisoformat(iso(instant, target))
    assert converted == instant
    assert converted.utcoffset() == target.utcoffset(instant)


@given(INSTANTS, st.text(max_size=20))
def test_unknown_time_zone_is_rejected(instant: datetime, name: str) -> None:
    try:
        ZoneInfo(name)
    except Exception:
        try:
            zone(name)
        except AppError as error:
            assert error.status == 422
        else:
            raise AssertionError("unknown zone accepted")
    else:
        zone(name)


def test_market_instant_uses_new_york_offset_in_winter_and_summer() -> None:
    from datetime import date, time

    winter = market_instant(date(2026, 1, 5), time(9, 30))
    summer = market_instant(date(2026, 7, 6), time(9, 30))
    assert winter.utcoffset() is not None and winter.utcoffset().total_seconds() == -5 * 3600
    assert summer.utcoffset() is not None and summer.utcoffset().total_seconds() == -4 * 3600
