from datetime import date, timedelta

import pytest

from acciones_ud.portfolio.domain.errors import InvalidPeriodError
from acciones_ud.portfolio.domain.period import parse


def test_inclusive_limits_and_dst():
    start = date(2024, 1, 1)
    assert parse(start, start + timedelta(days=365)).to == date(2024, 12, 31)
    for end, reason in [
        (start - timedelta(days=1), "from_after_to"),
        (start + timedelta(days=366), "too_long"),
    ]:
        with pytest.raises(InvalidPeriodError) as caught:
            parse(start, end)
        assert caught.value.reason == reason
    since, until = parse(date(2024, 3, 10), date(2024, 3, 10)).bounds()
    assert (until - since).total_seconds() == 23 * 3600
