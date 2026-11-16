from decimal import Decimal

from acciones_ud.portfolio.domain.model import RiskInputs
from acciones_ud.portfolio.domain.risk import profile


def test_insufficient_data():
    result = profile(RiskInputs(90, 0, Decimal(0), [], None))
    assert result.risk_score is None
    assert result.classification == "insufficient_data"
    assert result.equity_unavailable
