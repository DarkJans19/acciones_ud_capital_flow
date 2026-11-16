from dataclasses import replace
from decimal import Decimal as D

import pytest

from acciones_ud.portfolio.domain.model import RawPosition, ViewSettings
from acciones_ud.portfolio.domain.valuation import arrange, value


@pytest.mark.parametrize("sort", ["symbol", "market_value", "gain_loss", "allocation"])
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_arrange(sort, direction):
    values = [
        value(RawPosition(s, "NYSE", D(1), D(1), D(1), D(p)), None, D(0))
        for s, p in [("B", 2), ("A", 2), ("C", 3)]
    ]
    visible, totals = arrange(values, ViewSettings("table", sort, direction, D(2)))
    expected = (
        ["A", "B", "C"]
        if direction == "asc"
        else ["C", "B", "A"]
        if sort == "symbol"
        else ["C", "A", "B"]
    )
    assert [p.symbol for p in visible] == expected
    hidden, hidden_totals = arrange(values, replace(ViewSettings(), hide_threshold=D(3)))
    assert [p.symbol for p in hidden] == ["C"]
    assert hidden_totals == totals
