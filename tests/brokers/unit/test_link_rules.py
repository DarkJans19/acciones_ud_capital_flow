from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from acciones_ud.brokers.domain.entities import Link
from acciones_ud.brokers.domain.entities import LinkAction as A
from acciones_ud.brokers.domain.entities import LinkStatus as S
from acciones_ud.brokers.domain.errors import InvalidLinkStateError
from acciones_ud.brokers.domain.link_state_machine import effective_status, transition


def test_link_expiry_boundary_and_terminal_state():
    now = datetime(2026, 11, 16, tzinfo=UTC)
    link = Link(uuid4(), uuid4(), uuid4(), S.REQUESTED, now, now + timedelta(days=7), "v1", now)
    assert (
        effective_status(link, now + timedelta(days=7) - timedelta(microseconds=1), 7)
        == S.REQUESTED
    )
    assert effective_status(link, now + timedelta(days=7), 7) == S.EXPIRED
    with pytest.raises(InvalidLinkStateError):
        transition(S.ENDED, A.ACCEPT)
