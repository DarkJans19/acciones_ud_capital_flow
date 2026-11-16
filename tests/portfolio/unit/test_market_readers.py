from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from acciones_ud.portfolio.adapters.outbound.market_data.report_notifier import ReportNotifier
from acciones_ud.portfolio.adapters.outbound.market_data.session_reader import SessionReader


async def test_session_uses_closed_calendar_days():
    calendar = SimpleNamespace(
        calendar=AsyncMock(
            return_value=SimpleNamespace(
                days=[
                    SimpleNamespace(date=date(2026, 1, 1), close_at=None),
                    SimpleNamespace(
                        date=date(2026, 1, 2), close_at=datetime(2026, 1, 2, 21, tzinfo=UTC)
                    ),
                    SimpleNamespace(
                        date=date(2026, 1, 5), close_at=datetime(2026, 1, 5, 21, tzinfo=UTC)
                    ),
                ]
            )
        )
    )
    assert await SessionReader(lambda: calendar).last_closed_session(
        datetime(2026, 1, 5, 20, tzinfo=UTC)
    ) == date(2026, 1, 2)


async def test_no_recipient_is_not_notified():
    @asynccontextmanager
    async def directory():
        yield SimpleNamespace(recipient=AsyncMock(return_value=None))

    notifier = AsyncMock()
    assert not await ReportNotifier(directory, notifier).notify(uuid4(), {})
    notifier.notify.assert_not_called()
