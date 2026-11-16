from decimal import Decimal, localcontext


def rate(
    realized_period: Decimal, unrealized: Decimal, current_cost: Decimal, sold_cost_period: Decimal
) -> Decimal | None:
    with localcontext() as ctx:
        ctx.prec = 40
        denominator = current_cost + sold_cost_period
        return (realized_period + unrealized) / denominator * 100 if denominator else None
