import asyncio
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, localcontext
from uuid import UUID

from acciones_ud.portfolio.application import dtos
from acciones_ud.portfolio.application.portfolio_service import PortfolioService
from acciones_ud.portfolio.domain import model as m
from acciones_ud.portfolio.domain import risk, rounding
from acciones_ud.portfolio.domain.ports import EquityPort, ExecutionQueryPort, InstrumentPort
from acciones_ud.shared.domain.alpaca_errors import AlpacaError
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError


class RiskProfileService:
    def __init__(
        self,
        portfolio: PortfolioService,
        executions: ExecutionQueryPort,
        instruments: InstrumentPort,
        equity: EquityPort,
        clock: Clock,
        window_days: int,
    ) -> None:
        self.portfolio, self.executions, self.instruments = portfolio, executions, instruments
        self.equity_port, self.clock, self.window_days = equity, clock, window_days

    async def profile(self, user_id: UUID) -> m.RiskProfile:
        now = self.clock.now()
        snapshot, executions = await asyncio.gather(
            self.portfolio.snapshot(user_id),
            self.executions.list(user_id, until=now, since=now - timedelta(days=self.window_days)),
        )
        try:
            equity = await self.equity_port.equity(snapshot.account.alpaca_account_id)
        except (AppError, AlpacaError):
            equity = None
        symbols = {e.symbol for e in executions}
        info = await self.instruments.classify(symbols)
        with localcontext() as ctx:
            ctx.prec = 40
            volume = sum((e.qty * e.price for e in executions), Decimal(0))
            result = risk.profile(
                m.RiskInputs(
                    self.window_days,
                    len(executions),
                    volume,
                    [p.market_value for p in snapshot.values],
                    equity,
                )
            )
            allocation = rounding.shares({p.symbol: p.market_value for p in snapshot.values})
            metrics = dtos.document(
                {
                    "execution_count": len(executions),
                    "executions_per_week": rounding.pct(
                        Decimal(len(executions)) * 7 / self.window_days
                    ),
                    "volume": rounding.money(volume),
                    "markets": sorted(
                        {info[s].market if s in info else "unknown" for s in symbols}
                    ),
                    "instruments": sorted(symbols),
                    "asset_distribution": allocation,
                    "window_from": now - timedelta(days=self.window_days),
                    "window_to": now,
                }
            )
        return replace(
            result,
            f=rounding.pct(result.f),
            c=rounding.pct(result.c),
            e=rounding.pct(result.e),
            t=rounding.pct(result.t),
            metrics=metrics,
        )
