from dataclasses import asdict
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.brokers.adapters.outbound.persistence import models as t
from acciones_ud.brokers.adapters.outbound.persistence.repository import Repository
from acciones_ud.brokers.domain.entities import Rating


class RatingRepository(Repository[Rating]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.ratings, Rating)

    async def upsert(self, value: Rating) -> Rating:
        statement = insert(t.ratings).values(**asdict(value))
        result_statement = statement.on_conflict_do_update(
            index_elements=[t.ratings.c.link_id],
            set_={
                "stars": statement.excluded.stars,
                "comment": statement.excluded.comment,
                "updated_at": statement.excluded.updated_at,
            },
        ).returning(t.ratings)
        return self.record((await self.session.execute(result_statement)).mappings().one())

    async def page(
        self, broker_id: UUID, cursor: str | None, limit: int
    ) -> tuple[list[Rating], str | None]:
        statement = sa.select(t.ratings).where(t.ratings.c.broker_id == broker_id)
        return await self.paginated(statement, "updated_at", "link_id", cursor, limit)
