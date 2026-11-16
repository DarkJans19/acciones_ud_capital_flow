from decimal import Decimal as D
from uuid import uuid4

import pytest

from acciones_ud.portfolio.domain.model import RawPosition
from acciones_ud.shared.domain.errors import AppError
from tests.portfolio.fakes import portfolio


async def test_fallback_mismatch_and_hidden_totals(caplog):
    service, source, alpaca = portfolio()
    alpaca.positions["private-account"] = [RawPosition("A", "NYSE", D(2), D(1), D(10), D(12))]
    result = await service.positions(source.account.user_id)
    position = result.positions[0]
    assert position.price_source == "alpaca_position"
    assert position.reserved_qty == 1 and position.reconciliation_mismatch
    assert "portfolio.reconciliation_mismatch" in caplog.text
    assert "private-account" not in caplog.text
    source.prices["A"] = D(13)
    assert (await service.positions(source.account.user_id)).totals.market_value == D(26)


async def test_unlinked_and_unrelated_client_stop_before_alpaca():
    service, source, alpaca = portfolio()
    source.account = None
    with pytest.raises(AppError) as caught:
        await service.positions(uuid4())
    assert caught.value.code == "ACCOUNT_NOT_LINKED"
    with pytest.raises(AppError) as caught:
        await service.client_positions(uuid4(), uuid4())
    assert caught.value.code == "NOT_FOUND"
    assert alpaca.calls == 0
