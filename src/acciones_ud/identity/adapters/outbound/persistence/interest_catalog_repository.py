import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


class InterestCatalogRepository:
    """RFP-08: read the shared tables without depending on Market Data application code."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def known_interests(self) -> list[str]:
        rows = await self.session.execute(
            sa.text(
                "SELECT code AS value FROM markets UNION "
                "SELECT DISTINCT sector FROM instruments WHERE sector IS NOT NULL"
            )
        )
        values: list[object] = list(rows.scalars())
        return [str(value) for value in values]
