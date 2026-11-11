import asyncio
import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from acciones_ud.config.settings import get_settings


@pytest.mark.db
def test_existing_email_variant_is_never_promoted_or_replaced(migrated_database: str) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from acciones_ud.identity.adapters.outbound.persistence import tables as t
    from acciones_ud.identity.adapters.outbound.persistence.user_repository import UserRepository
    from acciones_ud.identity.domain.registration import build_new_user
    from acciones_ud.shared.domain.clock import SystemClock
    from acciones_ud.shared.infrastructure.db import build_engine

    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "0001_identity_schema")

    async def insert_existing() -> object:
        engine = build_engine(migrated_database)
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            record, _ = build_new_user(
                "investor",
                {
                    "first_names": "Existing",
                    "last_names": "Account",
                    "email": "  " + os.environ["INITIAL_ADMIN_EMAIL"].upper() + "  ",
                    "phone": "+15555550100",
                    "country": "US",
                    "password": "ExistingPassword123",
                    "terms_accepted": True,
                    "monthly_report": False,
                },
            )
            record.update(
                password_hash=os.environ["INITIAL_ADMIN_PASSWORD_HASH"],
                terms_accepted_at=SystemClock().now(),
            )
            async with factory() as session, session.begin():
                return await UserRepository(session).insert(record, None)
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
