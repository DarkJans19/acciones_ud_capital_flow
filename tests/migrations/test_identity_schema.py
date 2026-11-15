import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.domain.preferences import CHANNELS, EVENT_TYPES


@pytest.mark.db
async def test_identity_seed_and_rls(db_session: AsyncSession) -> None:
    roles = (await db_session.execute(text("SELECT code FROM roles"))).scalars().all()
    assert set(roles) == {"investor", "broker", "administrator"}
    assert (
        await db_session.execute(text("SELECT count(*) FROM notification_preferences"))
    ).scalar() == len(CHANNELS) * len(EVENT_TYPES)
    assert (await db_session.execute(text("SELECT count(*) FROM users"))).scalar() == 1
    tables = (
        (
            await db_session.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' AND NOT rowsecurity"
                )
            )
        )
        .scalars()
        .all()
    )
    assert not tables
