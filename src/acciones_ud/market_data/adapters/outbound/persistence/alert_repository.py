"""RF-26: price alerts persistence."""

from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.market_data.domain.entities import AlertStatus, Comparator, PriceAlert

ALERT_COLUMNS = (
    "id, user_id, symbol, comparator, threshold, status, "
    "last_evaluated_price, created_at, triggered_at"
)


def _alert(row: Any) -> PriceAlert:
    mapping = cast("dict[str, Any]", row._mapping)
    return PriceAlert(
        id=mapping["id"],
        symbol=str(mapping["symbol"]),
        comparator=Comparator(str(mapping["comparator"])),
        threshold=mapping["threshold"],
        status=AlertStatus(str(mapping["status"])),
        created_at=mapping["created_at"],
        triggered_at=mapping["triggered_at"],
        user_id=mapping["user_id"],
        last_evaluated_price=mapping["last_evaluated_price"],
    )


class AlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self, user_id: UUID) -> list[PriceAlert]:
        rows = await self.session.execute(
            sa.text(
                f"SELECT {ALERT_COLUMNS} FROM price_alerts WHERE user_id = :user "
                "ORDER BY created_at NULLS LAST, id"
            ),
            {"user": user_id},
        )
        return [_alert(row) for row in rows]

    async def get(self, user_id: UUID, alert_id: UUID) -> PriceAlert | None:
        row = (
            await self.session.execute(
                sa.text(
                    f"SELECT {ALERT_COLUMNS} FROM price_alerts "
                    "WHERE id = :id AND user_id = :user"
                ),
                {"id": alert_id, "user": user_id},
            )
        ).first()
        return None if row is None else _alert(row)

    async def create(
        self, user_id: UUID, symbol: str, comparator: str, threshold: Decimal, now: datetime
    ) -> PriceAlert:
        alert_id = uuid4()
        await self.session.execute(
            sa.text(
                "INSERT INTO price_alerts "
                "(id, user_id, symbol, comparator, threshold, status, created_at) "
                "VALUES (:id, :user, :symbol, :comparator, :threshold, 'active', :now)"
            ),
            {
                "id": alert_id,
                "user": user_id,
                "symbol": symbol,
                "comparator": comparator,
                "threshold": threshold,
                "now": now,
            },
        )
        return PriceAlert(
            id=alert_id,
            symbol=symbol,
            comparator=Comparator(comparator),
            threshold=threshold,
            status=AlertStatus.ACTIVE,
            created_at=now,
            user_id=user_id,
        )

    async def set_status(
        self, user_id: UUID, alert_id: UUID, status: str
    ) -> PriceAlert | None:
        row = (
            await self.session.execute(
                sa.text(
                    "UPDATE price_alerts SET status = :status "
                    "WHERE id = :id AND user_id = :user "
                    f"RETURNING {ALERT_COLUMNS}"
                ),
                {"id": alert_id, "user": user_id, "status": status},
            )
        ).first()
        return None if row is None else _alert(row)

    async def delete(self, user_id: UUID, alert_id: UUID) -> bool:
        row = (
            await self.session.execute(
                sa.text(
                    "DELETE FROM price_alerts WHERE id = :id AND user_id = :user "
                    "RETURNING id"
                ),
                {"id": alert_id, "user": user_id},
            )
        ).first()
        return row is not None

    async def active_grouped(self) -> dict[str, list[PriceAlert]]:
        rows = await self.session.execute(
            sa.text(
                f"SELECT {ALERT_COLUMNS} FROM price_alerts WHERE status = 'active' "
                "ORDER BY symbol, id"
            )
        )
        grouped: dict[str, list[PriceAlert]] = {}
        for row in rows:
            alert = _alert(row)
            grouped.setdefault(alert.symbol, []).append(alert)
        return grouped

    async def lock_active(self, alert_id: UUID) -> PriceAlert | None:
        row = (
            await self.session.execute(
                sa.text(
                    f"SELECT {ALERT_COLUMNS} FROM price_alerts "
                    "WHERE id = :id AND status = 'active' FOR UPDATE"
                ),
                {"id": alert_id},
            )
        ).first()
        return None if row is None else _alert(row)

    async def record_price(self, alert_id: UUID, price: Decimal) -> None:
        await self.session.execute(
            sa.text(
                "UPDATE price_alerts SET last_evaluated_price = :price WHERE id = :id"
            ),
            {"id": alert_id, "price": price},
        )

    async def trigger(self, alert_id: UUID, price: Decimal, now: datetime) -> bool:
        row = (
            await self.session.execute(
                sa.text(
                    "UPDATE price_alerts SET status = 'triggered', "
                    "triggered_at = :now, last_evaluated_price = :price "
                    "WHERE id = :id AND status = 'active' RETURNING id"
                ),
                {"id": alert_id, "price": price, "now": now},
            )
        ).first()
        return row is not None
