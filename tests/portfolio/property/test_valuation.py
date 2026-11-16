from decimal import Decimal, localcontext

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.portfolio.domain.model import RawPosition
from acciones_ud.portfolio.domain.valuation import value
from tests.portfolio.property.test_pnl import amount, price


# Feature: portfolio-mod-05, Property 1: Valoración de una posición
@settings(max_examples=100)
@given(
    amount,
    price,
    price,
    st.one_of(st.none(), price),
    amount,
    st.decimals(min_value=0, max_value=1, places=9),
)
def test_valuation(quantity, average, current, quote, reserved, fraction):
    available = quantity * fraction
    raw = RawPosition("A", "NYSE", quantity, available, average, current)
    actual = value(raw, quote, reserved)
    with localcontext() as ctx:
        ctx.prec = 40
        assert actual.reserved_qty == quantity - available + reserved
        assert actual.price == (current if quote is None else quote)
        assert actual.price_source == ("alpaca_position" if quote is None else "market_data")
        assert actual.market_value == quantity * actual.price
        assert actual.unrealized_pnl == actual.market_value - quantity * average
        assert actual.cost_basis >= Decimal(0)
