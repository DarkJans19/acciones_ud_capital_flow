"""HTTP contracts for watchlists, alerts and notifications (RF-26)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from acciones_ud.market_data.domain.alerts import MAX_THRESHOLD
from acciones_ud.market_data.domain.entities import Notification, PriceAlert, Watchlist


class WatchlistIn(BaseModel):
    name: str


class WatchlistOut(BaseModel):
    id: str
    name: str
    symbols: list[str]

    @classmethod
    def of(cls, watchlist: Watchlist) -> "WatchlistOut":
        return cls(
            id=str(watchlist.id), name=watchlist.name, symbols=list(watchlist.symbols)
        )


class WatchlistSymbolIn(BaseModel):
    symbol: str


class AlertIn(BaseModel):
    symbol: str
    comparator: Literal["above", "below", "crosses"]
    threshold: Decimal = Field(gt=0, le=MAX_THRESHOLD)


class AlertOut(BaseModel):
    id: str
    symbol: str
    comparator: str
    threshold: Decimal
    status: str
    created_at: datetime | None
    triggered_at: datetime | None

    @classmethod
    def of(cls, alert: PriceAlert) -> "AlertOut":
        return cls(
            id=str(alert.id),
            symbol=alert.symbol,
            comparator=alert.comparator.value,
            threshold=alert.threshold,
            status=alert.status.value,
            created_at=alert.created_at,
            triggered_at=alert.triggered_at,
        )


class NotificationOut(BaseModel):
    id: str
    event_type: str
    payload: dict[str, object]
    created_at: datetime

    @classmethod
    def of(cls, notification: Notification) -> "NotificationOut":
        return cls(
            id=str(notification.id),
            event_type=notification.event_type,
            payload=notification.payload,
            created_at=notification.created_at,
        )
