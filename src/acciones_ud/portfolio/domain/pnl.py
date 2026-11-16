from collections.abc import Callable, Iterable
from dataclasses import replace
from decimal import Decimal, localcontext

from acciones_ud.portfolio.domain.decimal_math import add
from acciones_ud.portfolio.domain.model import ExecutionRecord, RealizedEvent, SymbolLedger


def replay(
    executions: Iterable[ExecutionRecord],
    commission: Callable[[ExecutionRecord], Decimal] = lambda _: Decimal(0),
) -> dict[str, SymbolLedger]:
    ledgers: dict[str, SymbolLedger] = {}
    with localcontext() as ctx:
        ctx.prec = 40
        for execution in sorted(executions, key=lambda e: (e.executed_at, e.execution_id)):
            prior = ledgers.get(execution.symbol, SymbolLedger(execution.symbol))
            if execution.side == "buy":
                current = replace(
                    prior,
                    qty=add(prior.qty, execution.qty),
                    total_cost=add(prior.total_cost, execution.qty * execution.price),
                )
            else:
                quantity = min(execution.qty, prior.qty)
                cost = (
                    prior.total_cost
                    if quantity == prior.qty
                    else prior.total_cost * quantity / prior.qty
                )
                gross = add(quantity * execution.price, cost.copy_negate())
                # A wholly unmatched sale has no computed result, including commission.
                net = add(gross, commission(execution).copy_negate()) if quantity else Decimal(0)
                event = RealizedEvent(
                    execution.execution_id, execution.executed_at, quantity, gross, net, cost
                )
                current = replace(
                    prior,
                    qty=prior.qty - quantity,
                    total_cost=add(prior.total_cost, cost.copy_negate()),
                    realized_gross=add(prior.realized_gross, gross),
                    realized_net=add(prior.realized_net, net),
                    sold_cost=add(prior.sold_cost, cost),
                    mismatch=prior.mismatch or execution.qty > prior.qty,
                    events=[*prior.events, event],
                )
            ledgers[execution.symbol] = current
    return ledgers


def average_cost(ledger: SymbolLedger) -> Decimal | None:
    with localcontext() as ctx:
        ctx.prec = 40
        return ledger.total_cost / ledger.qty if ledger.qty else None
