"""HTTP contract for the dashboard (RFP-08)."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from acciones_ud.market_data.application.dashboard import DashboardView


class DashboardInstrumentOut(BaseModel):
    symbol: str
    name: str
    price: Decimal | None
    quote_timestamp: datetime | None
    quote_unavailable: bool


class DashboardOut(BaseModel):
    market_status: str | None
    market_status_unavailable: bool
    level: str | None
    beginner: bool
    source: str
    instruments: list[DashboardInstrumentOut]

    @classmethod
    def of(cls, view: DashboardView) -> "DashboardOut":
        return cls(
            market_status=view.market_status,
            market_status_unavailable=view.market_status_unavailable,
            level=view.data.level,
            beginner=view.data.beginner,
            source=view.data.source,
            instruments=[
                DashboardInstrumentOut(
                    symbol=item.symbol,
                    name=item.name,
                    price=item.price,
                    quote_timestamp=item.quote_timestamp,
                    quote_unavailable=item.quote_unavailable,
                )
                for item in view.data.instruments
            ],
        )
