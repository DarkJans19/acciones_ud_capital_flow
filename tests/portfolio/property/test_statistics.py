from dataclasses import replace
from decimal import Decimal as D
from decimal import localcontext

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.portfolio.domain.model import InstrumentInfo
from acciones_ud.portfolio.domain.statistics import summarize
from tests.portfolio.property.test_pnl import records, trades


# Feature: portfolio-mod-05, Property 5: Desgloses de participación
@settings(max_examples=100)
@given(trades, st.lists(st.sampled_from([None, "", "tech"]), min_size=3, max_size=3))
def test_breakdowns(rows, sectors):
    executions = [replace(e, symbol=str(i % 4)) for i, e in enumerate(records(rows))]
    info = {str(i): InstrumentInfo(str(i), "NYSE", sector) for i, sector in enumerate(sectors)}
    result = summarize(executions, info)
    with localcontext() as ctx:
        ctx.prec = 40
        for breakdown in [result.by_market, result.by_instrument, result.by_sector]:
            assert sum((s.volume for s in breakdown), D(0)) == result.volume
            assert sum((s.percentage for s in breakdown), D(0)) == D("100.00")
            for share in breakdown:
                assert share.percentage >= 0
                assert share.percentage.as_tuple().exponent == -2
                assert abs(share.percentage - share.volume / result.volume * 100) < D("0.01")
        expected = sum(
            (
                e.qty * e.price
                for e in executions
                if e.symbol not in info or not info[e.symbol].sector
            ),
            D(0),
        )
        actual = next((s.volume for s in result.by_sector if s.key == "unclassified"), D(0))
        assert actual == expected
