"""One latest snapshot row per instrument (13.6, 13.14)."""

from datetime import datetime
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.market_data.domain.entities import Snapshot, StoredSnapshot

from .tables import instrument_snapshots


def _stored(row: Any) -> StoredSnapshot:
    mapping = cast("dict[str, Any]", row._mapping)
    return StoredSnapshot(
        snapshot=Snapshot(
            last_trade_price=mapping["last_trade_price"],
            bid_price=mapping["bid_price"],
            ask_price=mapping["ask_price"],
            bid_size=mapping["bid_size"],
            ask_size=mapping["ask_size"],
            daily_volume=mapping["daily_volume"],
            quote_updated_at=mapping["quote_updated_at"],
            feed=str(mapping["feed"]),
        ),
        retrieved_at=mapping["retrieved_at"],
    )


class SnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, symbol: str) -> StoredSnapshot | None:
        row = (
            await self.session.execute(
                sa.text(
                    """
                    SELECT last_trade_price, bid_price, ask_price, bid_size, ask_size,
                           daily_volume, quote_updated_at, feed, retrieved_at
                    FROM instrument_snapshots
                    WHERE symbol = :symbol
                    """
                ),
                {"symbol": symbol},
            )
        ).first()
        return None if row is None else _stored(row)

    async def save(self, symbol: str, snapshot: Snapshot, retrieved_at: datetime) -> None:
        values: dict[str, object] = {
            "symbol": symbol,
            "last_trade_price": snapshot.last_trade_price,
            "bid_price": snapshot.bid_price,
            "ask_price": snapshot.ask_price,
            "bid_size": snapshot.bid_size,
            "ask_size": snapshot.ask_size,
            "daily_volume": snapshot.daily_volume,
            "quote_updated_at": snapshot.quote_updated_at,
            "feed": snapshot.feed,
            "retrieved_at": retrieved_at,
        }
        statement = pg_insert(instrument_snapshots).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[instrument_snapshots.c.symbol],
            set_={
                "last_trade_price": statement.excluded.last_trade_price,
                "bid_price": statement.excluded.bid_price,
                "ask_price": statement.excluded.ask_price,
                "bid_size": statement.excluded.bid_size,
                "ask_size": statement.excluded.ask_size,
                "daily_volume": statement.excluded.daily_volume,
                "quote_updated_at": statement.excluded.quote_updated_at,
                "feed": statement.excluded.feed,
                "retrieved_at": statement.excluded.retrieved_at,
            },
        )
        await self.session.execute(statement)
