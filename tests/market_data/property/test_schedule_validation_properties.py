# Feature: identity-market-backend, Property 29: Schedule validation

from datetime import time

import pytest
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.schedule import validate_default, validate_override
from acciones_ud.shared.domain.errors import AppError

TIMES = st.one_of(
    st.none(),
    st.integers(min_value=0, max_value=23).flatmap(
        lambda hour: st.integers(min_value=0, max_value=59).map(
            lambda minute: time(hour=hour, minute=minute)
        )
    ),
)


@given(closed=st.booleans(), open_time=TIMES, close_time=TIMES)
def test_override_validation(closed: bool, open_time: time | None, close_time: time | None) -> None:
    valid = (
        (closed and open_time is None and close_time is None)
        or (
            not closed
            and open_time is not None
            and close_time is not None
            and close_time > open_time
        )
    )
    if valid:
        validate_override(closed, open_time, close_time)
    else:
        with pytest.raises(AppError) as error:
            validate_override(closed, open_time, close_time)
        assert error.value.status == 422


@given(first=TIMES, second=TIMES)
def test_default_schedule_validation(first: time | None, second: time | None) -> None:
    valid = first is not None and second is not None and second > first
    if valid:
        validate_default(first, second)
    else:
        with pytest.raises(AppError):
            validate_default(first, second)
