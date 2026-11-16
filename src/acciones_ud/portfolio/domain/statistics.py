from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal, localcontext

from acciones_ud.portfolio.domain.model import ExecutionRecord, InstrumentInfo, Share, Statistics
from acciones_ud.portfolio.domain.rounding import shares


def summarize(executions: Iterable[ExecutionRecord], info: dict[str, InstrumentInfo]) -> Statistics:
    rows = list(executions)
    groups: list[dict[str, Decimal]] = [defaultdict(Decimal) for _ in range(3)]
    with localcontext() as ctx:
        ctx.prec = 40
        for row in rows:
            instrument = info.get(row.symbol)
            keys = (
                instrument.market if instrument else "unknown",
                row.symbol,
                (instrument.sector or "unclassified") if instrument else "unclassified",
            )
            for group, key in zip(groups, keys, strict=True):
                group[key] += row.qty * row.price
        breakdowns = []
        for group in groups:
            percentages = shares(group)
            breakdowns.append(
                [Share(k, group[k], percentages.get(k, Decimal(0))) for k in sorted(group)]
            )
        return Statistics(
            len(rows),
            sum(e.side == "buy" for e in rows),
            sum(e.side == "sell" for e in rows),
            sum((e.qty * e.price for e in rows), Decimal(0)),
            *breakdowns,
        )
