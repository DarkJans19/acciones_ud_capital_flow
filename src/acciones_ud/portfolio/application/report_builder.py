import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from uuid import UUID

from acciones_ud.portfolio.application import dtos
from acciones_ud.portfolio.application.portfolio_service import PortfolioService
from acciones_ud.portfolio.domain import model as m
from acciones_ud.portfolio.domain import pnl, profitability, rounding, valuation
from acciones_ud.portfolio.domain.decimal_math import add
from acciones_ud.portfolio.domain.period import parse
from acciones_ud.portfolio.domain.ports import CommissionPort, ExecutionQueryPort


@dataclass(frozen=True)
class ReportAmounts:
    market_value: Decimal = Decimal(0)
    current_cost: Decimal = Decimal(0)
    sold_cost: Decimal = Decimal(0)
    volume: Decimal = Decimal(0)
    realized_gross: Decimal = Decimal(0)
    realized_net: Decimal = Decimal(0)
    unrealized_pnl: Decimal = Decimal(0)
    commissions: Decimal = Decimal(0)


@dataclass(frozen=True)
class BuiltReport:
    content: dict[str, object]
    positions_as_of: datetime
    executions: list[m.ExecutionRecord]
    amounts: ReportAmounts


def amount_document(amounts: ReportAmounts) -> dict[str, object]:
    profitability_rate = profitability.rate(
        amounts.realized_gross, amounts.unrealized_pnl, amounts.current_cost, amounts.sold_cost
    )
    return dtos.document(
        {
            "market_value": rounding.money(amounts.market_value),
            "cost_basis": rounding.money(amounts.current_cost),
            "volume": rounding.money(amounts.volume),
            "realized_pnl": {
                "gross": rounding.money(amounts.realized_gross),
                "net": rounding.money(amounts.realized_net),
            },
            "unrealized_pnl": rounding.money(amounts.unrealized_pnl),
            "commissions": rounding.money(amounts.commissions),
            "profitability": rounding.pct(profitability_rate)
            if profitability_rate is not None
            else None,
        }
    )


class ReportBuilder:
    def __init__(
        self,
        portfolio: PortfolioService,
        executions: ExecutionQueryPort,
        commissions: CommissionPort,
    ) -> None:
        self.portfolio, self.ledger, self.commissions = portfolio, executions, commissions

    async def build(self, user_id: UUID, period: m.Period) -> BuiltReport:
        since, until = parse(period.from_, period.to).bounds()
        snapshot, executions = await asyncio.gather(
            self.portfolio.snapshot(user_id), self.ledger.list(user_id, until=until)
        )
        within = [e for e in executions if since <= e.executed_at < until]
        ledgers = pnl.replay(executions, lambda e: self.commissions.commission(e).amount)
        events = [
            event
            for ledger in ledgers.values()
            for event in ledger.events
            if since <= event.executed_at < until
        ]
        _, totals = valuation.arrange(snapshot.values, m.ViewSettings())
        with localcontext() as ctx:
            ctx.prec = 40
            amounts = ReportAmounts(
                totals.market_value,
                totals.cost_basis,
                add(*(e.cost_removed for e in events)),
                add(*(e.qty * e.price for e in within)),
                add(*(e.gross for e in events)),
                add(*(e.net for e in events)),
                totals.unrealized_pnl,
                add(*(self.commissions.commission(e).amount for e in within)),
            )
        content = {
            **amount_document(amounts),
            "currency": "USD",
            "period": {"from": period.from_.isoformat(), "to": period.to.isoformat()},
            "positions_as_of": snapshot.positions_as_of.isoformat(),
            "positions": [dtos.serialize(dtos.position(p)) for p in snapshot.values],
            "executions_count": len(within),
            "executions": [
                dtos.serialize(dtos.execution(e, self.commissions.commission(e))) for e in within
            ],
            "asset_summary": dtos.document(
                {
                    "market_value": rounding.money(totals.market_value),
                    "cost_basis": rounding.money(totals.cost_basis),
                    "position_count": len(snapshot.values),
                }
            ),
        }
        return BuiltReport(content, snapshot.positions_as_of, within, amounts)
