import asyncio
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from acciones_ud.config.settings import get_settings


@pytest.mark.db
def test_existing_email_variant_is_never_promoted_or_replaced(migrated_database: str) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from acciones_ud.identity.adapters.outbound.persistence import tables as t
    from acciones_ud.shared.domain.clock import SystemClock
    from acciones_ud.shared.infrastructure.db import build_engine

    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "0001_identity_schema")

    async def insert_existing() -> object:
        engine = build_engine(migrated_database)
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            # Seed only the 0001 user row. The current repository also inserts
            # preferences introduced in later revisions, which do not exist yet.
            existing_id = uuid4()
            email = os.environ["INITIAL_ADMIN_EMAIL"]
            record = dict(
                id=existing_id,
                first_names="Existing",
                last_names="Account",
                email="  " + email.upper() + "  ",
                email_normalized=email.strip().lower(),
                phone="+15555550100",
                country="US",
                password_hash=os.environ["INITIAL_ADMIN_PASSWORD_HASH"],
                terms_accepted_at=SystemClock().now(),
                monthly_report=False,
            )
            async with factory() as session, session.begin():
                await session.execute(sa.insert(t.users).values(**record))
            return existing_id
        finally:
            await engine.dispose()

    async def verify(existing_id: object) -> None:
        engine = build_engine(migrated_database)
        try:
            async with engine.connect() as connection:
                row = (await connection.execute(sa.select(t.users))).mappings().one()
                assert row["id"] == existing_id and row["first_names"] == "Existing"
                assert (
                    await connection.execute(
                        sa.select(sa.func.count()).select_from(t.role_assignments)
                    )
                ).scalar() == 0
        finally:
            await engine.dispose()

    try:
        existing = asyncio.run(insert_existing())
        get_settings.cache_clear()
        command.upgrade(config, "head")
        asyncio.run(verify(existing))
    finally:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
