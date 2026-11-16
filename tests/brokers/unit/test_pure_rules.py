from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D
from uuid import uuid4

import pytest

from acciones_ud.brokers.domain.entities import Link, LinkStatus, Period
from acciones_ud.brokers.domain.errors import InvalidPeriodError, QuoteUnavailableError
from acciones_ud.brokers.domain.estimates import estimated_cost, reference_price, requires_totp
from acciones_ud.brokers.domain.periods import link_overlaps, to_utc_range


def test_estimates_use_half_even_and_totp_includes_equality():
    assert estimated_cost(D("1"), D("10.005"), D("0")) == D("10.00")
    assert estimated_cost(D("3.5"), D("100"), D("0.02")) == D("357.00")
    assert requires_totp(D("100"), D("100"))
    assert reference_price("limit", D("123"), None) == D("123")
    with pytest.raises(QuoteUnavailableError):
        reference_price("market", None, None)


def test_period_uses_new_york_dst_and_rejects_reversed_dates():
    start, end = to_utc_range(Period(date(2026, 3, 8), date(2026, 3, 8)))
    assert start == datetime(2026, 3, 8, 5, tzinfo=UTC)
    assert (end - start).total_seconds() == 23 * 3600
    with pytest.raises(InvalidPeriodError):
        to_utc_range(Period(date(2026, 11, 17), date(2026, 11, 16)))


def test_link_history_interval_includes_active_links_and_terminal_response():
    now = datetime(2026, 11, 16, tzinfo=UTC)
    link = Link(
        uuid4(),
        uuid4(),
        uuid4(),
        LinkStatus.ACTIVE,
        now - timedelta(days=10),
        now - timedelta(days=3),
        "v1",
        now - timedelta(days=10),
        responded_at=now - timedelta(days=8),
        started_at=now - timedelta(days=8),
    )
    assert link_overlaps(link, now - timedelta(days=1), now + timedelta(days=1), now)
    ended = replace(link, status=LinkStatus.ENDED, ended_at=now - timedelta(days=2))
    assert not link_overlaps(ended, now - timedelta(days=1), now, now)
    declined = replace(link, status=LinkStatus.DECLINED)
    assert not link_overlaps(declined, now - timedelta(days=1), now, now)
