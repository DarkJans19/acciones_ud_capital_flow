"""Typed dataclass mapping for small transaction-scoped SQL repositories.

Schemas are migrated by Alembic; this module never creates database tables.
"""

import types
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, get_args, get_origin, get_type_hints
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession


def entity_table(
    metadata: sa.MetaData,
    name: str,
    entity: type[Any],
    keys: tuple[str, ...],
    *,
    unique: tuple[str, ...] = (),
    references: dict[str, str] | None = None,
    constraints: tuple[sa.schema.SchemaItem, ...] = (),
) -> sa.Table:
    columns: list[sa.Column[Any]] = []
    hints = get_type_hints(entity)
    for field in fields(entity):
        hint = hints[field.name]
        optional = get_origin(hint) is types.UnionType and type(None) in get_args(hint)
        if optional:
            hint = next(arg for arg in get_args(hint) if arg is not type(None))
        sql_type: sa.types.TypeEngine[Any]
        if hint is UUID:
            sql_type = sa.Uuid()
        elif hint is datetime:
            sql_type = sa.DateTime(timezone=True)
        elif hint is Decimal:
            sql_type = sa.Numeric(20, 9)
        elif hint is bool:
            sql_type = sa.Boolean()
        elif hint is int:
            sql_type = sa.Integer()
        elif get_origin(hint) in {dict, list, tuple}:
            sql_type = JSONB()
        else:
            sql_type = sa.Text()
        foreign = (references or {}).get(field.name)
        args = [sa.ForeignKey(foreign)] if foreign else []
        columns.append(
            sa.Column(
                field.name,
                sql_type,
                *args,
                primary_key=field.name in keys,
                nullable=optional and field.name not in keys,
                unique=field.name in unique,
            )
        )
    return sa.Table(name, metadata, *columns, *constraints)


class EntityRepository[T]:
    def __init__(self, session: AsyncSession, table: sa.Table, entity: type[T]) -> None:
        self.session, self.table, self.entity = session, table, entity
        self.entity_fields = frozenset(get_type_hints(entity))

    def _where(self, filters: dict[str, object]) -> list[sa.ColumnElement[bool]]:
        return [self.table.c[key] == value for key, value in filters.items()]

    async def get(self, **filters: object) -> T | None:
        result = await self.session.execute(
            sa.select(self.table).where(*self._where(filters)).limit(1)
        )
        row = result.mappings().first()
        return (
            self.entity(**{k: v for k, v in row.items() if k in self.entity_fields})
            if row is not None
            else None
        )

    async def list(self, **filters: object) -> list[T]:
        result = await self.session.execute(sa.select(self.table).where(*self._where(filters)))
        return [
            self.entity(**{k: v for k, v in row.items() if k in self.entity_fields})
            for row in result.mappings()
        ]

    async def insert(self, value: T) -> bool:
        assert is_dataclass(value) and not isinstance(value, type)
        result = await self.session.execute(
            insert(self.table)
            .values(**asdict(value))
            .on_conflict_do_nothing()
            .returning(*self.table.primary_key.columns)
        )
        return result.first() is not None

    async def save(self, value: T, **expected: object) -> bool:
        assert is_dataclass(value) and not isinstance(value, type)
        values = asdict(value)
        if "updated_at" in self.table.c and "updated_at" not in values:
            values["updated_at"] = sa.func.now()
        filters = {c.name: values[c.name] for c in self.table.primary_key.columns}
        filters.update(expected)
        result = await self.session.execute(
            sa.update(self.table)
            .where(*self._where(filters))
            .values(**values)
            .returning(*self.table.primary_key.columns)
        )
        return result.first() is not None

    async def delete(self, **filters: object) -> None:
        await self.session.execute(sa.delete(self.table).where(*self._where(filters)))
