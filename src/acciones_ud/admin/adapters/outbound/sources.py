"""G25: explicit, read-only access to the existing modules' persisted data."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from acciones_ud.admin.domain.model import Raw
from acciones_ud.admin.domain.periods import Period
from acciones_ud.shared.domain.clock import Clock, SystemClock


class MarketCatalog:
    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock or SystemClock()

    async def markets(self) -> list[Raw]:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        today = self.clock.now().astimezone(ZoneInfo("America/New_York")).date()
        async with unit_of_work() as session:
            result = await session.execute(sa.text("SELECT * FROM markets ORDER BY code"))
            markets = [dict(row) for row in result.mappings()]
            overrides = await session.execute(
                sa.text("""SELECT * FROM schedule_overrides
                WHERE date >= :start AND date <= :end ORDER BY date,id"""),
                {"start": today, "end": today + timedelta(days=90)},
            )
            rows = [dict(row) for row in overrides.mappings()]
        for market in markets:
            market["overrides"] = [r for r in rows if r["market_code"] == market["code"]]
            market["default_schedule"] = (
                {
                    "open_time": market["default_open_time"],
                    "close_time": market["default_close_time"],
                }
                if market["default_open_time"] is not None
                else None
            )
        return markets

    async def exchange_of(self, symbol: str) -> str | None:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        async with unit_of_work() as session:
            value = await session.scalar(
                sa.text("SELECT exchange FROM instruments WHERE symbol=:s"), {"s": symbol}
            )
            return str(value) if value is not None else None


class UserReader:
    async def summary(self, user_id: UUID, at: datetime) -> Raw | None:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        async with unit_of_work() as session:
            result = await session.execute(
                sa.text("""SELECT id,created_at FROM users
                WHERE id = :id"""),
                {"id": user_id},
            )
            row = result.mappings().first()
            if row is None:
                return None
            roles = await session.execute(
                sa.text("""SELECT DISTINCT role_code FROM role_assignments
                WHERE user_id = :id AND status <> 'CANCELLED' AND valid_from <= :at
                AND (valid_to IS NULL OR valid_to > :at) ORDER BY role_code"""),
                {"id": user_id, "at": at},
            )
            return {**dict(row), "roles": list(roles.scalars())}

    async def display_names(self, ids: Sequence[UUID]) -> dict[UUID, str]:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        if not ids:
            return {}
        async with unit_of_work() as session:
            result = await session.execute(
                sa.text("""SELECT id,first_names,last_names FROM users
                WHERE id IN :ids""").bindparams(sa.bindparam("ids", expanding=True)),
                {"ids": ids},
            )
            return {row[0]: f"{row[1]} {row[2]}" for row in result}


class KpiSource:
    async def inputs(self, period: Period, at: datetime) -> Raw:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        start, end = period.bounds()
        instant = min(end, at)
        params = {"start": start, "end": end, "at": instant}
        async with unit_of_work() as session:
            total = await session.scalar(
                sa.text("SELECT count(*) FROM users WHERE created_at<:end"), params
            )
            registrations = await session.execute(
                sa.text("""SELECT investor_level,interests
                FROM users WHERE created_at >= :start AND created_at < :end"""),
                params,
            )
            active = await session.scalar(
                sa.text("""SELECT count(DISTINCT user_id) FROM auth_events
                WHERE kind='mfa_verify' AND result='success' AND occurred_at >= :start
                AND occurred_at < :end"""),
                params,
            )
            payments = await session.execute(
                sa.text("""SELECT amount,currency FROM subscription_payments
                WHERE result='paid' AND occurred_at >= :start AND occurred_at < :end"""),
                params,
            )
            subscriptions = await session.scalar(
                sa.text("""SELECT count(DISTINCT subscription_id)
                FROM subscription_payments WHERE result='paid' AND occurred_at <= :at
                AND period_start <= :at AND period_end > :at"""),
                params,
            )
            investors = await session.execute(
                sa.text("""SELECT u.investor_level,EXISTS(
                SELECT 1 FROM broker_links l WHERE l.investor_id=u.id AND l.started_at <= :at
                AND (l.ended_at IS NULL OR l.ended_at > :at)) AS with_broker
                FROM users u WHERE u.created_at <= :at AND u.account_status='active' AND EXISTS (
                  SELECT 1 FROM role_assignments r WHERE r.user_id=u.id AND r.role_code='investor'
                  AND r.status <> 'CANCELLED' AND r.valid_from <= :at
                  AND (r.valid_to IS NULL OR r.valid_to > :at))"""),
                params,
            )
            return {
                "registered_users": total,
                "active_users": active,
                "registrations": [dict(r) for r in registrations.mappings()],
                "payments": [dict(r) for r in payments.mappings()],
                "active_subscriptions": subscriptions,
                "investors": [dict(r) for r in investors.mappings()],
            }
