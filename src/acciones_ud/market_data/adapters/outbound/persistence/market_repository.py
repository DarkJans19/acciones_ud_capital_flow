"""RF-27: markets, default schedules and schedule overrides persistence."""

from datetime import date, time
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.market_data.domain.entities import Market, ScheduleOverride
from acciones_ud.shared.domain.errors import AppError, ErrorCode

MARKET_COLUMNS = "code, name, timezone, default_open_time, default_close_time"
OVERRIDE_COLUMNS = "id, market_code, date, closed, open_time, close_time"


def _market(row: Any) -> Market:
    mapping = cast("dict[str, Any]", row._mapping)
    return Market(
        code=str(mapping["code"]),
        name=str(mapping["name"]),
        timezone=str(mapping["timezone"]),
        default_open_time=mapping["default_open_time"],
        default_close_time=mapping["default_close_time"],
    )


def _override(row: Any) -> ScheduleOverride:
    mapping = cast("dict[str, Any]", row._mapping)
    return ScheduleOverride(
        id=mapping["id"],
        market_code=str(mapping["market_code"]),
        date=mapping["date"],
        closed=bool(mapping["closed"]),
        open_time=mapping["open_time"],
        close_time=mapping["close_time"],
    )


class MarketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def all_markets(self) -> list[Market]:
        rows = await self.session.execute(
            sa.text(f"SELECT {MARKET_COLUMNS} FROM markets ORDER BY code")
        )
        return [_market(row) for row in rows]

    async def market(self, code: str) -> Market | None:
        row = (
            await self.session.execute(
                sa.text(f"SELECT {MARKET_COLUMNS} FROM markets WHERE code = :code"),
                {"code": code},
            )
        ).first()
        return None if row is None else _market(row)

    async def set_default_schedule(
        self, code: str, open_at: time, close_at: time
    ) -> Market | None:
        row = (
            await self.session.execute(
                sa.text(
                    "UPDATE markets SET default_open_time = :open_at, "
                    "default_close_time = :close_at WHERE code = :code "
                    f"RETURNING {MARKET_COLUMNS}"
                ),
                {"code": code, "open_at": open_at, "close_at": close_at},
            )
        ).first()
        return None if row is None else _market(row)

    async def clear_default_schedule(self, code: str) -> bool:
        row = (
            await self.session.execute(
                sa.text(
                    "UPDATE markets SET default_open_time = NULL, default_close_time = NULL "
                    "WHERE code = :code RETURNING code"
                ),
                {"code": code},
            )
        ).first()
        return row is not None

    async def overrides(
        self, code: str, start: date | None, end: date | None
    ) -> list[ScheduleOverride]:
        rows = await self.session.execute(
            sa.text(
                f"SELECT {OVERRIDE_COLUMNS} FROM schedule_overrides "
                "WHERE market_code = :code "
                "AND (:start IS NULL OR date >= :start) "
                "AND (:end IS NULL OR date <= :end) "
                "ORDER BY date"
            ),
            {"code": code, "start": start, "end": end},
        )
        return [_override(row) for row in rows]

    async def override(self, code: str, override_id: UUID) -> ScheduleOverride | None:
        row = (
            await self.session.execute(
                sa.text(
                    f"SELECT {OVERRIDE_COLUMNS} FROM schedule_overrides "
                    "WHERE market_code = :code AND id = :id"
                ),
                {"code": code, "id": override_id},
            )
        ).first()
        return None if row is None else _override(row)

    async def add_override(self, override: ScheduleOverride) -> ScheduleOverride:
        try:
            await self.session.execute(
                sa.text(
                    "INSERT INTO schedule_overrides "
                    "(id, market_code, date, closed, open_time, close_time) "
                    "VALUES (:id, :code, :date, :closed, :open_time, :close_time)"
                ),
                {
                    "id": override.id,
                    "code": override.market_code,
                    "date": override.date,
                    "closed": override.closed,
                    "open_time": override.open_time,
                    "close_time": override.close_time,
                },
            )
        except IntegrityError:
            raise AppError(
                409,
                ErrorCode.OVERRIDE_EXISTS,
                "A schedule override already exists for that market and date.",
            ) from None
        return override

    async def update_override(self, override: ScheduleOverride) -> ScheduleOverride | None:
        row = (
            await self.session.execute(
                sa.text(
                    "UPDATE schedule_overrides SET closed = :closed, "
                    "open_time = :open_time, close_time = :close_time "
                    "WHERE market_code = :code AND id = :id "
                    f"RETURNING {OVERRIDE_COLUMNS}"
                ),
                {
                    "code": override.market_code,
                    "id": override.id,
                    "closed": override.closed,
                    "open_time": override.open_time,
                    "close_time": override.close_time,
                },
            )
        ).first()
        return None if row is None else _override(row)

    async def delete_override(self, code: str, override_id: UUID) -> bool:
        row = (
            await self.session.execute(
                sa.text(
                    "DELETE FROM schedule_overrides WHERE market_code = :code AND id = :id "
                    "RETURNING id"
                ),
                {"code": code, "id": override_id},
            )
        ).first()
        return row is not None
