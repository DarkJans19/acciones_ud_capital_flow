"""RF-44: restricted repository surface for append-only dataclasses."""

import builtins

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.shared.infrastructure.entity_repository import EntityRepository


class EvidenceRepository[T]:
    def __init__(self, session: AsyncSession, table: sa.Table, entity: type[T]) -> None:
        self._rows = EntityRepository(session, table, entity)

    async def get(self, **filters: object) -> T | None:
        return await self._rows.get(**filters)

    async def list(self, **filters: object) -> builtins.list[T]:
        return await self._rows.list(**filters)

    async def insert(self, value: T) -> bool:
        return await self._rows.insert(value)
