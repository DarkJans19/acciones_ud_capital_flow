import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from acciones_ud.identity.adapters.outbound.persistence.rbac_repository import RbacRepository
from acciones_ud.identity.adapters.outbound.persistence.tables import role_assignments, users
from acciones_ud.identity.adapters.outbound.persistence.user_repository import UserRepository
from acciones_ud.identity.adapters.outbound.security.passwords import PasswordHasher
from acciones_ud.identity.domain.registration import build_new_user
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.identity.test_registration_security import payload


@pytest.mark.db
async def test_duplicate_registration_and_atomic_activation(migrated_database: str) -> None:
    from acciones_ud.shared.infrastructure.db import build_engine

    engine = build_engine(migrated_database)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    email = uuid4().hex + "@example.com"
    user, _ = build_new_user(
        "broker",
        {**payload(), "email": email, "firm_name": "Test firm", "license_number": "TEST123"},
    )
    user["password_hash"] = PasswordHasher().hash("Password123")
    user["terms_accepted_at"] = datetime.now(UTC)

    async def register() -> object:
        try:
            async with factory() as session, session.begin():
                return await UserRepository(session).insert(user, None)
        except AppError as exc:
            return exc.code

    try:
        outcomes = await asyncio.gather(*(register() for _ in range(4)))
        assert outcomes.count(ErrorCode.EMAIL_ALREADY_REGISTERED) == 3
        async with factory() as session:
            user_id = (
                await session.execute(
                    sa.select(users.c.id).where(users.c.email_normalized == email)
                )
            ).scalar_one()
            assert not (
                await session.execute(
                    sa.select(role_assignments.c.id).where(role_assignments.c.user_id == user_id)
                )
            ).all()

        async def activate() -> object:
            try:
                async with factory() as session, session.begin():
                    return await RbacRepository(session).activate_broker(user_id, datetime.now(UTC))
            except AppError as exc:
                return exc.code

        activated = await asyncio.gather(*(activate() for _ in range(4)))
        assert activated.count(ErrorCode.BROKER_NOT_PENDING) == 3
        async with factory() as session:
            assert (
                len(
                    (
                        await session.execute(
                            sa.select(role_assignments).where(role_assignments.c.user_id == user_id)
                        )
                    ).all()
                )
                == 1
            )
    finally:
        async with factory() as session, session.begin():
            await session.execute(users.delete().where(users.c.email_normalized == email))
        await engine.dispose()
