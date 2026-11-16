from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from acciones_ud.portfolio.adapters.outbound.persistence.report_repository import ReportRepository
from acciones_ud.portfolio.adapters.outbound.persistence.tables import reports
from acciones_ud.portfolio.domain.model import Period, Report


@pytest.mark.db
async def test_scheduled_uniqueness_pagination_and_immutability(db_session):
    owner = (await db_session.execute(sa.text("SELECT id FROM users LIMIT 1"))).scalar_one()
    now = datetime.now(UTC)
    original = Report(
        uuid4(),
        owner,
        "investor",
        "daily_summary",
        Period(date(2026, 1, 1), date(2026, 1, 1)),
        now,
        {"volume": "1.00"},
        now,
    )
    repo = ReportRepository(db_session)
    assert await repo.add(original)
    assert not await repo.add(replace(original, id=uuid4()))
    second = replace(
        original, id=uuid4(), type="on_demand", generated_at=now + timedelta(seconds=1)
    )
    assert await repo.add(second)
    first_page = await repo.list_page(owner, None, None, 1)
    assert first_page.items == [second]
    assert (await repo.list_page(owner, None, first_page.next_cursor, 1)).items == [original]
    assert await repo.get(uuid4(), original.id) is None
    await repo.mark_notified(original.id, now)
    assert (await repo.get(owner, original.id)).notified_at == now
    with pytest.raises(DBAPIError):
        async with db_session.begin_nested():
            await db_session.execute(
                sa.update(reports)
                .where(reports.c.id == original.id)
                .values(content={"changed": True})
            )
