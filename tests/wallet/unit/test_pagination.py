from datetime import datetime
from types import SimpleNamespace

from acciones_ud.wallet.application.dtos import paginate


def test_cursor_sorts_instants_across_timezones() -> None:
    early = SimpleNamespace(id="a", created_at=datetime.fromisoformat("2026-11-13T09:00:00+05:00"))
    late = SimpleNamespace(id="b", created_at=datetime.fromisoformat("2026-11-13T08:00:00+00:00"))
    first = paginate([early, late], 1, None)
    assert first.items == [late] and first.next_cursor
    second = paginate([early, late], 1, first.next_cursor)
    assert second.items == [early] and second.next_cursor is None
