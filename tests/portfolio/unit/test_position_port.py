from decimal import Decimal as D

import pytest

from acciones_ud.portfolio.adapters.outbound.alpaca.fake_positions import FakePositions
from acciones_ud.portfolio.application.position_port import PortfolioPositionPort
from acciones_ud.portfolio.domain.model import RawPosition
from acciones_ud.shared.domain.alpaca_errors import AlpacaRateLimited


async def test_available_absent_and_error_propagation():
    source = FakePositions()
    port = PortfolioPositionPort(source)
    assert await port.qty_available("account", "A") == 0
    source.positions["account"] = [RawPosition("A", "NYSE", D(10), D(7), D(10), D(11))]
    assert await port.qty_available("account", "A") == 7
    source.error = AlpacaRateLimited()
    with pytest.raises(AlpacaRateLimited):
        await port.qty_available("account", "A")
