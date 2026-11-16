from decimal import ROUND_HALF_EVEN, localcontext
from decimal import Decimal as D

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.portfolio.domain.model import RiskInputs
from acciones_ud.portfolio.domain.profitability import rate
from acciones_ud.portfolio.domain.risk import profile
from tests.portfolio.property.test_pnl import amount

nonnegative = st.one_of(st.just(D(0)), amount)


# Feature: portfolio-mod-05, Property 6: Risk_Profiler contra el modelo de referencia
@settings(max_examples=100)
@given(
    st.integers(7, 365),
    st.integers(0, 10000),
    nonnegative,
    st.lists(nonnegative, max_size=20),
    st.one_of(st.none(), nonnegative),
)
def test_risk_model(days, count, volume, values, equity):
    actual = profile(RiskInputs(days, count, volume, values, equity))
    with localcontext() as ctx:
        ctx.prec = 40
        f = min(D(100), D(count) * 70 / days)
        total = sum(values, D(0))
        c = sum(((v / total) ** 2 for v in values), D(0)) * 100 if total else D(0)
        e = min(D(100), total / equity * 100) if equity else D(0)
        t = min(D(100), volume / equity / 4 * 100) if equity else D(0)
        assert (actual.f, actual.c, actual.e, actual.t) == (f, c, e, t)
        assert all(0 <= x <= 100 for x in (actual.f, actual.c, actual.e, actual.t))
        assert actual.equity_unavailable == (not equity)
        if not count and not values:
            assert actual.classification == "insufficient_data"
            assert actual.risk_score is None
        else:
            expected = f * D(".25") + c * D(".30") + e * D(".25") + t * D(".20")
            expected = expected.quantize(D(".01"), rounding=ROUND_HALF_EVEN)
            assert actual.risk_score == expected
            assert actual.classification == (
                "conservative"
                if expected <= D("33.33")
                else "moderate"
                if expected <= D("66.66")
                else "aggressive"
            )


# Feature: portfolio-mod-05, Property 7: Concentración monótona
@settings(max_examples=100)
@given(amount, amount, st.decimals(min_value="0.000000001", max_value=1, places=9))
def test_concentration(a, b, fraction):
    a, b = sorted([a, b])
    delta = a * fraction
    before = profile(RiskInputs(90, 1, D(0), [a, b], D(100)))
    after = profile(RiskInputs(90, 1, D(0), [a - delta, b + delta], D(100)))
    assert after.c >= before.c


# Feature: portfolio-mod-05, Property 8: Rentabilidad del periodo
@settings(max_examples=100)
@given(
    st.decimals(min_value="-1000000000", max_value="1000000000", places=4),
    st.decimals(min_value="-1000000000", max_value="1000000000", places=4),
    nonnegative,
    nonnegative,
)
def test_profitability(realized, unrealized, current, sold):
    with localcontext() as ctx:
        ctx.prec = 40
        actual = rate(realized, unrealized, current, sold)
        assert actual == (
            (realized + unrealized) / (current + sold) * 100 if current + sold else None
        )
