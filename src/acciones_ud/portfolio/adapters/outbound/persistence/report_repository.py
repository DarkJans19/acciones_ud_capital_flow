from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.portfolio.adapters.outbound.persistence.tables import reports as t
from acciones_ud.portfolio.domain.model import Page, Period, Report, ReportType
from acciones_ud.portfolio.domain.pagination import decode, encode, invalid, validate_size


def report(row: sa.RowMapping) -> Report:
    return Report(
        row["id"],
        row["owner_id"],
        row["owner_role"],
        row["type"],
        Period(row["period_from"], row["period_to"]),
        row["positions_as_of"],
        row["content"],
        row["generated_at"],
        row["notified_at"],
    )


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, report: Report) -> bool:
        statement = insert(t).values(
            id=report.id,
            owner_id=report.owner_id,
            owner_role=report.owner_role,
            type=report.type,
            period_from=report.period.from_,
            period_to=report.period.to,
            positions_as_of=report.positions_as_of,
            content=report.content,
            generated_at=report.generated_at,
            notified_at=report.notified_at,
        )
        if report.type in {"daily_summary", "monthly"}:
            statement = statement.on_conflict_do_nothing(
                index_elements=[t.c.owner_id, t.c.type, t.c.period_from, t.c.period_to],
                index_where=sa.text("type IN ('daily_summary','monthly')"),
            )
        return (
            await self.session.execute(statement.returning(t.c.id))
        ).scalar_one_or_none() is not None

    async def get(self, owner_id: UUID, id: UUID) -> Report | None:
        row = (
            (await self.session.execute(sa.select(t).where(t.c.owner_id == owner_id, t.c.id == id)))
            .mappings()
            .first()
        )
        return report(row) if row else None

    async def scheduled(self, owner_id: UUID, type: ReportType, period: Period) -> Report | None:
        row = (
            (
                await self.session.execute(
                    sa.select(t).where(
                        t.c.owner_id == owner_id,
                        t.c.type == type,
                        t.c.period_from == period.from_,
                        t.c.period_to == period.to,
                    )
                )
            )
            .mappings()
            .first()
        )
        return report(row) if row else None

    async def list_page(
        self, owner_id: UUID, type: ReportType | None, cursor: str | None, size: int
    ) -> Page[Report]:
        validate_size(size)
        conditions = [t.c.owner_id == owner_id]
        if type is not None:
            conditions.append(t.c.type == type)
        if cursor:
            at, ident = decode(cursor)
            try:
                key = UUID(ident)
            except ValueError:
                raise invalid("cursor") from None
            conditions.append(sa.tuple_(t.c.generated_at, t.c.id) < (at, key))
        rows = (
            await self.session.execute(
                sa.select(t)
                .where(*conditions)
                .order_by(t.c.generated_at.desc(), t.c.id.desc())
                .limit(size + 1)
            )
        ).mappings()
        values = [report(row) for row in rows]
        selected = values[:size]
        next_cursor = (
            encode(selected[-1].generated_at, str(selected[-1].id)) if len(values) > size else None
        )
        return Page(selected, next_cursor)

    async def pending_notification(self) -> list[Report]:
        rows = (
            await self.session.execute(
                sa.select(t)
                .where(t.c.type.in_(["daily_summary", "monthly"]), t.c.notified_at.is_(None))
                .order_by(t.c.generated_at, t.c.id)
            )
        ).mappings()
        return [report(row) for row in rows]

    async def mark_notified(self, id: UUID, at: datetime) -> None:
        await self.session.execute(
            sa.update(t).where(t.c.id == id, t.c.notified_at.is_(None)).values(notified_at=at)
        )
