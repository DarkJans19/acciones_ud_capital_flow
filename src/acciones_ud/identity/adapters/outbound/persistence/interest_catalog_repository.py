import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.domain.interests import InterestOptions


class InterestCatalogRepository:
    """RFP-08: read the shared tables without depending on Market Data application code."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def known_interests(self) -> list[str]:
        options = await self.interest_options()
        return options["markets"] + options["sectors"]

    async def interest_options(self) -> InterestOptions:
        rows = await self.session.execute(
            sa.text(
                "SELECT 'markets' AS kind, code AS value FROM markets UNION "
                "SELECT 'sectors' AS kind, sector AS value FROM instruments "
                "WHERE sector IS NOT NULL AND length(sector) BETWEEN 1 AND 50 "
                "AND trim(sector) <> '' "
                "ORDER BY kind, value"
            )
        )
        options: InterestOptions = {"markets": [], "sectors": []}
        # Deterministic canonical spelling even if sector data differs only in case.
        seen: set[str] = set()
        for kind, raw_value in rows:
            value = str(raw_value)
            if value.lower() not in seen:
                options["markets" if kind == "markets" else "sectors"].append(value)
                seen.add(value.lower())
        return options
