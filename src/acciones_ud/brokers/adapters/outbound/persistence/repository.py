import base64
import builtins
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.brokers.domain import entities as e
from acciones_ud.brokers.domain.errors import ValidationError


def encode(at: datetime, ident: UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{ident}".encode()).decode()


def decode(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.b64decode(cursor.encode(), altchars=b"-_", validate=True).decode()
        at, ident = raw.split("|", 1)
        instant = datetime.fromisoformat(at)
        if instant.utcoffset() is None:
            raise ValueError()
        return instant, UUID(ident)
    except (ValueError, UnicodeError):
        raise ValidationError("cursor") from None


class Repository[T]:
    def __init__(self, session: AsyncSession, table: sa.Table, entity: type[T]) -> None:
        self.session, self.table, self.entity = session, table, entity

    def record(self, row: Mapping[Any, Any]) -> T:
        values = dict(row)
        for name in ("certifications", "evidence_message_ids"):
            if name in values:
                values[name] = tuple(values[name])
        if self.entity is e.Link:
            values["status"] = e.LinkStatus(values["status"])
        elif self.entity is e.Proposal:
            values["status"] = e.ProposalStatus(values["status"])
        return self.entity(**values)

    def predicates(self, filters: dict[str, object]) -> list[sa.ColumnElement[bool]]:
        return [self.table.c[key] == value for key, value in filters.items()]

    async def get(self, *, for_update: bool = False, **filters: object) -> T | None:
        statement = sa.select(self.table).where(*self.predicates(filters)).limit(1)
        if for_update:
            statement = statement.with_for_update()
        row = (await self.session.execute(statement)).mappings().first()
        return self.record(row) if row is not None else None

    async def list(self, **filters: object) -> builtins.list[T]:
        rows = (
            await self.session.execute(sa.select(self.table).where(*self.predicates(filters)))
        ).mappings()
        return [self.record(row) for row in rows]

    async def insert(self, value: T) -> bool:
        assert is_dataclass(value) and not isinstance(value, type)
        await self.session.execute(sa.insert(self.table).values(**asdict(value)))
        return True

    async def save(self, value: T, **expected: object) -> bool:
        assert is_dataclass(value) and not isinstance(value, type)
        values = asdict(value)
        filters = {c.name: values[c.name] for c in self.table.primary_key.columns}
        filters.update(expected)
        row = await self.session.execute(
            sa.update(self.table)
            .where(*self.predicates(filters))
            .values(**values)
            .returning(*self.table.primary_key.columns)
        )
        return row.first() is not None

    async def paginated(
        self,
        statement: sa.Select[Any],
        at: str,
        ident: str,
        cursor: str | None,
        limit: int,
        *,
        ascending: bool = False,
    ) -> tuple[builtins.list[T], str | None]:
        if not 1 <= limit <= 100:
            raise ValidationError("page_size")
        key = sa.tuple_(self.table.c[at], self.table.c[ident])
        if cursor:
            boundary = decode(cursor)
            statement = statement.where(key > boundary if ascending else key < boundary)
        columns = (self.table.c[at], self.table.c[ident])
        statement = statement.order_by(*(c.asc() if ascending else c.desc() for c in columns))
        rows = (await self.session.execute(statement.limit(limit + 1))).mappings().all()
        token = encode(rows[limit - 1][at], rows[limit - 1][ident]) if len(rows) > limit else None
        return [self.record(row) for row in rows[:limit]], token

    async def expired_batch(self, now: datetime, limit: int) -> builtins.list[T]:
        status = "requested" if self.entity is e.Link else "sent"
        rows = (
            await self.session.execute(
                sa.select(self.table)
                .where(
                    self.table.c.status == status,
                    self.table.c.expires_at <= now,
                )
                .order_by(self.table.c.expires_at, self.table.c.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).mappings()
        return [self.record(row) for row in rows]
