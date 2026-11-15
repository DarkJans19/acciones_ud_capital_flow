import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from acciones_ud.orders.adapters.outbound.persistence.tables import TABLES, keys, reservations
from acciones_ud.orders.adapters.outbound.persistence.unit_of_work import build_work
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.shared.domain.errors import AppError
from tests.orders.support import make_context


@pytest.mark.db
async def test_concurrent_creations_cannot_overreserve(migrated_database) -> None:
    from acciones_ud.shared.infrastructure.db import build_engine, translate_database_errors

    engine = build_engine(migrated_database)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    names = ["lock-" + uuid4().hex, "lock-" + uuid4().hex]
    async with factory() as session:
        owner = (await session.execute(sa.text("SELECT id FROM users LIMIT 1"))).scalar_one()

    @asynccontextmanager
    async def uow():
        async with translate_database_errors(), factory() as session, session.begin():
            yield build_work(session)

    gate = asyncio.Event()

    class SimultaneousBuyingPower:
        count = 0

        async def buying_power(self, account_id):
            self.count += 1
            if self.count == 2:
                gate.set()
            # Both external reads must finish before investor locking begins.
            await gate.wait()
            return Decimal("100.00")

    ctx, fake_user = make_context()
    ctx.accounts.values[owner] = replace(ctx.accounts.values[fake_user], user_id=owner)
    ctx.sessions.open = False
    ctx = replace(ctx, uow=uow, buying_power=SimultaneousBuyingPower())
    service = OrderService(ctx)
    request = OrderRequest("AAPL", "buy", Decimal(6), confirmed=True, schedule_if_closed=True)
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                service.create(owner, request, names[0]),
                service.create(owner, request, names[1]),
                return_exceptions=True,
            ),
            15,
        )
        errors = [result for result in results if isinstance(result, AppError)]
        assert len(errors) == 1 and errors[0].code == "INSUFFICIENT_BUYING_POWER"
        async with factory() as session:
            total = (
                await session.execute(
                    sa.select(sa.func.coalesce(sa.func.sum(reservations.c.amount), 0)).where(
                        reservations.c.user_id == owner, reservations.c.status == "active"
                    )
                )
            ).scalar_one()
            assert Decimal(0) < total <= Decimal("100.00")
    finally:
        async with factory() as session, session.begin():
            owned = (
                (
                    await session.execute(
                        sa.select(keys.c.order_id).where(
                            keys.c.user_id == owner, keys.c.idempotency_key.in_(names)
                        )
                    )
                )
                .scalars()
                .all()
            )
            for table in reversed(TABLES):
                if "order_id" in table.c:
                    await session.execute(sa.delete(table).where(table.c.order_id.in_(owned)))
                elif table.name == "orders":
                    await session.execute(sa.delete(table).where(table.c.id.in_(owned)))
        await engine.dispose()
