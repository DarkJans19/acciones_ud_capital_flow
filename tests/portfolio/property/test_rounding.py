from decimal import ROUND_HALF_EVEN, Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.portfolio.application import dtos
from acciones_ud.portfolio.domain import rounding
from acciones_ud.portfolio.domain.model import PositionValue, ViewSettings
from acciones_ud.portfolio.domain.valuation import arrange


# Feature: portfolio-mod-05, Property 9: Redondeo solo en la salida
@settings(max_examples=100)
@given(
    st.lists(
        st.decimals(
            min_value="-1000000000",
            max_value="1000000000",
            places=9,
            allow_nan=False,
            allow_infinity=False,
        ),
        max_size=50,
    )
)
def test_output_rounding(amounts):
    total = sum(amounts, Decimal(0))
    positions = [
        PositionValue(
            str(i),
            "NYSE",
            None,
            Decimal(1),
            Decimal(0),
            Decimal(1),
            "market_data",
            Decimal(0),
            value,
            Decimal(0),
            value,
        )
        for i, value in enumerate(amounts)
    ]
    _, totals = arrange(positions, ViewSettings())
    assert dtos.totals(totals).market_value == rounding.money(total)
    for function, scale in [
        (rounding.money, "0.01"),
        (rounding.qty, "0.000000001"),
        (rounding.price, "0.0001"),
        (rounding.pct, "0.01"),
    ]:
        assert function(total) == total.quantize(Decimal(scale), rounding=ROUND_HALF_EVEN)
    assert rounding.money(total) == total.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
