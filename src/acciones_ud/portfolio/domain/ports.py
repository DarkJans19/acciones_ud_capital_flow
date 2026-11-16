from contextlib import AbstractAsyncContextManager
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from acciones_ud.portfolio.domain import model as m


class LinkedAccountReader(Protocol):
    async def get(self, user_id: UUID) -> m.LinkedAccount | None: ...


class AlpacaPositionPort(Protocol):
    async def list(self, alpaca_account_id: str) -> list[m.RawPosition]: ...
    async def get(self, alpaca_account_id: str, symbol: str) -> m.RawPosition | None: ...


class ExecutionQueryPort(Protocol):
    async def list(
        self,
        user_id: UUID,
        until: datetime | None = None,
        since: datetime | None = None,
        symbol: str | None = None,
    ) -> list[m.ExecutionRecord]: ...
    async def list_page(
        self,
        user_id: UUID,
        since: datetime,
        until: datetime,
        symbol: str | None,
        cursor: m.PageCursor | None,
        size: int,
    ) -> m.Page[m.ExecutionRecord]: ...


class ReservationQueryPort(Protocol):
    async def active_share_reservations(self, user_id: UUID) -> dict[str, Decimal]: ...


class QuotePort(Protocol):
    async def last_price(self, symbol: str) -> Decimal | None: ...


class InstrumentPort(Protocol):
    async def classify(self, symbols: set[str]) -> dict[str, m.InstrumentInfo]: ...


class MarketSessionPort(Protocol):
    async def last_closed_session(self, at: datetime) -> date | None: ...


class ViewSettingsPort(Protocol):
    async def get(self, user_id: UUID) -> m.ViewSettings: ...


class ReportPreferencesPort(Protocol):
    async def daily_summary_investors(self) -> list[UUID]: ...
    async def monthly_report_investors(self) -> list[UUID]: ...


class EquityPort(Protocol):
    async def equity(self, alpaca_account_id: str) -> Decimal | None: ...


class CommissionPort(Protocol):
    def commission(self, execution: m.ExecutionRecord) -> m.CommissionQuote: ...


class BrokerClientPort(Protocol):
    async def linked_investors(self, broker_id: UUID) -> list[UUID]: ...
    async def is_linked(self, broker_id: UUID, investor_id: UUID) -> bool: ...


class ReportNotifierPort(Protocol):
    async def notify(self, user_id: UUID, payload: dict[str, object]) -> bool: ...


class ReportRepository(Protocol):
    async def add(self, report: m.Report) -> bool: ...
    async def get(self, owner_id: UUID, id: UUID) -> m.Report | None: ...
    async def list_page(
        self,
        owner_id: UUID,
        type: m.ReportType | None,
        cursor: str | None,
        size: int,
    ) -> m.Page[m.Report]: ...
    async def scheduled(
        self,
        owner_id: UUID,
        type: m.ReportType,
        period: m.Period,
    ) -> m.Report | None: ...
    async def pending_notification(self) -> list[m.Report]: ...
    async def mark_notified(self, id: UUID, at: datetime) -> None: ...


class ReportWork(Protocol):
    reports: ReportRepository


class ReportWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[ReportWork]: ...
