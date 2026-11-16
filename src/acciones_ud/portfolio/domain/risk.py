from decimal import Decimal, localcontext
from typing import Literal

from acciones_ud.portfolio.domain.model import RiskInputs, RiskProfile
from acciones_ud.portfolio.domain.rounding import pct


def profile(inputs: RiskInputs) -> RiskProfile:
    with localcontext() as ctx:
        ctx.prec = 40
        total = sum(inputs.market_values, Decimal(0))
        f = min(Decimal(100), Decimal(inputs.execution_count) * 70 / inputs.window_days)
        c = (
            sum(((v / total) ** 2 for v in inputs.market_values), Decimal(0)) * 100
            if total
            else Decimal(0)
        )
        unavailable = inputs.equity is None or inputs.equity <= 0
        e = t = Decimal(0)
        if not unavailable and inputs.equity is not None:
            e = min(Decimal(100), total / inputs.equity * 100)
            t = min(Decimal(100), inputs.traded_volume / inputs.equity / 4 * 100)
        if not inputs.execution_count and not inputs.market_values:
            return RiskProfile(
                inputs.window_days, f, c, e, t, None, "insufficient_data", unavailable
            )
        score = pct(
            Decimal("0.25") * f + Decimal("0.30") * c + Decimal("0.25") * e + Decimal("0.20") * t
        )
        classification: Literal["conservative", "moderate", "aggressive"]
        classification = (
            "conservative"
            if score <= Decimal("33.33")
            else "moderate"
            if score <= Decimal("66.66")
            else "aggressive"
        )
        return RiskProfile(inputs.window_days, f, c, e, t, score, classification, unavailable)
