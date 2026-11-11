"""Instrument catalog persistence: search, exchange list and catalog upsert."""

from datetime import datetime
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.market_data.domain.entities import Instrument, Market
from acciones_ud.market_data.domain.search import PAGE_SIZE
from acciones_ud.market_data.domain.symbols import validate_symbol

from .tables import instruments, markets

COLUMNS = (
    "symbol",
    "alpaca_asset_id",
    "name",
    "exchange",
    "asset_class",
    "status",
    "tradable",
    "marginable",
    "shortable",
    "easy_to_borrow",
    "fractionable",
    "sector",
    "listed",
    "updated_at",
)

# asyncpg rejects statements with more than 32767 bound parameters. With 10
# bound columns per instrument, 500 rows stay far below that ceiling.
UPSERT_BATCH_SIZE = 500

SEARCH_SQL = sa.text(
    """
    SELECT {columns}
    FROM instruments
    WHERE (symbol LIKE :prefix ESCAPE '\\' OR lower(name) LIKE :contains ESCAPE '\\')
      AND (CAST(:exchange AS text) IS NULL OR exchange = CAST(:exchange AS text))
      AND (CAST(:tradable AS boolean) IS NULL OR tradable = CAST(:tradable AS boolean))
    ORDER BY CASE
        WHEN symbol = :exact THEN 0
        WHEN symbol LIKE :prefix ESCAPE '\\' THEN 1
        ELSE 2
    END, symbol
    LIMIT :limit OFFSET :offset
    """.format(columns=", ".join(COLUMNS))
)

COUNT_SQL = sa.text(
    """
    SELECT count(*)
    FROM instruments
    WHERE (symbol LIKE :prefix ESCAPE '\\' OR lower(name) LIKE :contains ESCAPE '\\')
      AND (CAST(:exchange AS text) IS NULL OR exchange = CAST(:exchange AS text))
      AND (CAST(:tradable AS boolean) IS NULL OR tradable = CAST(:tradable AS boolean))
    """
)


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _instrument(row: Any) -> Instrument:
    mapping = cast("dict[str, Any]", row._mapping)
    sector = mapping["sector"]
    listed = mapping["listed"]
    return Instrument(
        symbol=str(mapping["symbol"]),
        name=str(mapping["name"]),
        exchange=str(mapping["exchange"]),
        asset_class=str(mapping["asset_class"]),
        status=str(mapping["status"]),
        tradable=bool(mapping["tradable"]),
        marginable=bool(mapping["marginable"]),
        shortable=bool(mapping["shortable"]),
        easy_to_borrow=bool(mapping["easy_to_borrow"]),
        fractionable=bool(mapping["fractionable"]),
        sector=None if sector is None else str(sector),
        listed=bool(listed),
        alpaca_asset_id=mapping["alpaca_asset_id"],
    )


def _values(asset: Instrument, now: datetime) -> dict[str, Any]:
    return {
        "symbol": asset.symbol.upper(),
        "alpaca_asset_id": asset.alpaca_asset_id,
        "name": asset.name,
        "exchange": asset.exchange,
        "asset_class": asset.asset_class,
        "status": asset.status,
        "tradable": asset.tradable,
        "marginable": asset.marginable,
        "shortable": asset.shortable,
        "easy_to_borrow": asset.easy_to_borrow,
        "fractionable": asset.fractionable,
        "sector": asset.sector,
        "listed": True,
        "updated_at": now,
    }


class InstrumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        exchange: str | None,
        classification: str | None,
        page: int,
        page_size: int = PAGE_SIZE,
    ) -> tuple[list[Instrument], int]:
        needle = escape_like(query)
        params = {
            "exact": query.upper(),
            "prefix": f"{needle.upper()}%",
            "contains": f"%{needle.lower()}%",
            "exchange": exchange,
            "tradable": None if classification is None else classification == "tradable",
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        rows = await self.session.execute(SEARCH_SQL, params)
        total = await self.session.scalar(COUNT_SQL, params)
        return [_instrument(row) for row in rows], int(total or 0)

    async def exchanges(self) -> list[Market]:
        rows = await self.session.execute(
            sa.text(
                """
                SELECT m.code, m.name, m.timezone, m.default_open_time, m.default_close_time
                FROM markets m
                WHERE EXISTS (
                    SELECT 1 FROM instruments i WHERE i.exchange = m.code AND i.listed
                )
                ORDER BY m.code
                """
            )
        )
        return [
            Market(
                code=str(row.code),
                name=str(row.name),
                timezone=str(row.timezone),
                default_open_time=row.default_open_time,
                default_close_time=row.default_close_time,
            )
            for row in rows
        ]

    async def exists(self, symbol: str) -> bool:
        value = await self.session.scalar(
            sa.text("SELECT EXISTS (SELECT 1 FROM instruments WHERE symbol = :symbol)"),
            {"symbol": validate_symbol(symbol)},
        )
        return bool(value)

    async def get(self, symbol: str) -> Instrument | None:
        statement = sa.text(
            "SELECT {} FROM instruments WHERE symbol = :symbol".format(", ".join(COLUMNS))
        )
        row = (
            await self.session.execute(statement, {"symbol": validate_symbol(symbol)})
        ).first()
        return None if row is None else _instrument(row)

    async def list_symbols(self) -> list[str]:
        rows = await self.session.execute(
            sa.text("SELECT symbol FROM instruments WHERE listed ORDER BY symbol")
        )
        values: list[object] = list(rows.scalars())
        return [str(value) for value in values]

    async def all_listed(self) -> list[Instrument]:
        rows = await self.session.execute(
            sa.text(
                "SELECT {} FROM instruments WHERE listed ORDER BY symbol".format(
                    ", ".join(COLUMNS)
                )
            )
        )
        return [_instrument(row) for row in rows]

    async def has_instruments(self) -> bool:
        value = await self.session.scalar(
            sa.text("SELECT EXISTS (SELECT 1 FROM instruments LIMIT 1)")
        )
        return bool(value)

    async def catalog_last_reload(self) -> datetime | None:
        value = await self.session.scalar(
            sa.text("SELECT last_reload_at FROM catalog_state WHERE id = 1")
        )
        return cast("datetime | None", value)

    async def set_catalog_last_reload(self, now: datetime) -> None:
        await self.session.execute(
            sa.text("UPDATE catalog_state SET last_reload_at = :now WHERE id = 1"),
            {"now": now},
        )

    async def upsert_catalog(self, assets: list[Instrument], now: datetime) -> None:
        symbols = [asset.symbol.upper() for asset in assets]
        if symbols:
            await self.session.execute(
                sa.text(
                    "UPDATE instruments SET listed = false "
                    "WHERE symbol <> ALL(CAST(:symbols AS text[]))"
                ),
                {"symbols": symbols},
            )
        else:
            await self.session.execute(
                sa.text("UPDATE instruments SET listed = false")
            )
        await self._upsert(assets, now)
        await self._ensure_exchanges({asset.exchange for asset in assets if asset.exchange})

    async def upsert_one(self, asset: Instrument, now: datetime) -> None:
        await self._upsert([asset], now)
        await self._ensure_exchanges({asset.exchange} if asset.exchange else set())

    async def _upsert(self, assets: list[Instrument], now: datetime) -> None:
        for start in range(0, len(assets), UPSERT_BATCH_SIZE):
            batch = assets[start : start + UPSERT_BATCH_SIZE]
            statement = pg_insert(instruments).values(
                [_values(asset, now) for asset in batch]
            )
            statement = statement.on_conflict_do_update(
                index_elements=[instruments.c.symbol],
                set_={
                    "alpaca_asset_id": statement.excluded.alpaca_asset_id,
                    "name": statement.excluded.name,
                    "exchange": statement.excluded.exchange,
                    "asset_class": statement.excluded.asset_class,
                    "status": statement.excluded.status,
                    "tradable": statement.excluded.tradable,
                    "marginable": statement.excluded.marginable,
                    "shortable": statement.excluded.shortable,
                    "easy_to_borrow": statement.excluded.easy_to_borrow,
                    "fractionable": statement.excluded.fractionable,
                    "listed": True,
                    "updated_at": statement.excluded.updated_at,
                },
            )
            await self.session.execute(statement)

    async def _ensure_exchanges(self, codes: set[str]) -> None:
        if not codes:
            return
        result = await self.session.execute(sa.select(markets.c.code))
        existing: set[str] = set(result.scalars())
        for code in sorted(codes - existing):
            await self.session.execute(
                pg_insert(markets)
                .values(code=code, name=code, timezone="America/New_York")
                .on_conflict_do_nothing(index_elements=[markets.c.code])
            )


__all__ = ["InstrumentRepository", "escape_like"]
