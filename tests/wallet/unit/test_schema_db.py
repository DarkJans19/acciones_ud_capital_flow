import pytest
from sqlalchemy import text


@pytest.mark.db
async def test_wallet_constraints_and_rls(db_session) -> None:
    rows = (
        await db_session.execute(
            text(
                "SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public' "
                "AND (tablename LIKE 'wallet_%' OR tablename IN "
                "('subscriptions','subscription_payments','stripe_events'))"
            )
        )
    ).all()
    assert len(rows) == 8 and all(row.rowsecurity for row in rows)
