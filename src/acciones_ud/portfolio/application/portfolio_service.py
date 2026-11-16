import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from acciones_ud.portfolio.application import dtos
from acciones_ud.portfolio.domain import model as m
from acciones_ud.portfolio.domain import pnl, valuation
from acciones_ud.portfolio.domain.errors import AccountNotLinkedError, NotFoundError
from acciones_ud.portfolio.domain.pagination import decode, validate_size
from acciones_ud.portfolio.domain.period import parse
from acciones_ud.portfolio.domain.ports import (
    AlpacaPositionPort,
    BrokerClientPort,
    CommissionPort,
    ExecutionQueryPort,
    InstrumentPort,
    LinkedAccountReader,
    QuotePort,
    ReservationQueryPort,
    ViewSettingsPort,
)
from acciones_ud.shared.domain.alpaca_errors import AlpacaError, to_app_error
from acciones_ud.shared.domain.clock import Clock

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PortfolioSnapshot:
    account: m.LinkedAccount
    values: list[m.PositionValue]
    settings: m.ViewSettings
    positions_as_of: datetime


class PortfolioService:
    def __init__(
        self,
        accounts: LinkedAccountReader,
        alpaca: AlpacaPositionPort,
        executions: ExecutionQueryPort,
        reservations: ReservationQueryPort,
        quotes: QuotePort,
        instruments: InstrumentPort,
        views: ViewSettingsPort,
        commissions: CommissionPort,
        brokers: BrokerClientPort,
        clock: Clock,
    ) -> None:
        self.accounts, self.alpaca, self.ledger = accounts, alpaca, executions
        self.reservations, self.quotes, self.instruments = reservations, quotes, instruments
        self.views, self.commissions, self.brokers, self.clock = views, commissions, brokers, clock

    async def linked(self, user_id: UUID) -> m.LinkedAccount:
        account = await self.accounts.get(user_id)
        if account is None:
            raise AccountNotLinkedError()
        return account

    async def snapshot(self, user_id: UUID) -> PortfolioSnapshot:
        account = await self.linked(user_id)
        now = self.clock.now()
        try:
            raw, reserved, executions, settings = await asyncio.gather(
                self.alpaca.list(account.alpaca_account_id),
                self.reservations.active_share_reservations(user_id),
                self.ledger.list(user_id, until=now),
                self.views.get(user_id),
            )
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        raw = [p for p in raw if p.qty > 0]
        symbols = sorted({p.symbol for p in raw})
        info, prices = await asyncio.gather(
            self.instruments.classify(set(symbols)),
            asyncio.gather(*(self._quote(s) for s in symbols)),
        )
        quotes = dict(zip(symbols, prices, strict=True))
        ledgers = pnl.replay(executions)
        values = []
        for position in raw:
            ledger = ledgers.get(position.symbol, m.SymbolLedger(position.symbol))
            mismatch = ledger.mismatch or ledger.qty != position.qty
            if mismatch:
                logger.warning(
                    "portfolio.reconciliation_mismatch symbol=%s alpaca_qty=%s executions_qty=%s",
                    position.symbol,
                    position.qty,
                    ledger.qty,
                )
            instrument = info.get(position.symbol)
            values.append(
                replace(
                    valuation.value(
                        position, quotes[position.symbol], reserved.get(position.symbol, Decimal(0))
                    ),
                    sector=instrument.sector if instrument else None,
                    reconciliation_mismatch=mismatch,
                )
            )
        return PortfolioSnapshot(account, values, settings, now)

    async def _quote(self, symbol: str) -> Decimal | None:
        try:
            return await self.quotes.last_price(symbol)
        except AlpacaError:
            return None

    async def positions(self, user_id: UUID) -> dtos.PositionsView:
        snapshot = await self.snapshot(user_id)
        visible, totals = valuation.arrange(snapshot.values, snapshot.settings)
        return dtos.PositionsView(
            [dtos.position(p) for p in visible],
            dtos.totals(totals),
            snapshot.settings.view_type,
            snapshot.positions_as_of,
        )

    async def client_positions(self, broker_id: UUID, investor_id: UUID) -> dtos.PositionsView:
        if not await self.brokers.is_linked(broker_id, investor_id):
            raise NotFoundError()
        return await self.positions(investor_id)

    async def executions(
        self,
        user_id: UUID,
        period: m.Period,
        symbol: str | None = None,
        cursor: str | None = None,
        size: int = 50,
    ) -> m.Page[dtos.ExecutionView]:
        validate_size(size)
        if cursor:
            decode(cursor)
        since, until = parse(period.from_, period.to).bounds()
        page = await self.ledger.list_page(user_id, since, until, symbol, cursor, size)
        return m.Page(
            [dtos.execution(e, self.commissions.commission(e)) for e in page.items],
            page.next_cursor,
        )
