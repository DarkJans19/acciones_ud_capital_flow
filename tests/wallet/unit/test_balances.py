from datetime import UTC, datetime
from uuid import uuid4

import pytest

from acciones_ud.shared.domain.alpaca_errors import AlpacaRateLimited, AlpacaUnavailable
from acciones_ud.wallet.adapters.outbound.alpaca.fake_funding import FakeFunding
from acciones_ud.wallet.application.wallet_service import WalletService
from tests.support.clock import FakeClock
from tests.wallet.fakes import MemoryFactory


class StatusWriter:
    async def update_status(self, user_id, status, at):
        raise AssertionError("Status should not be written when Alpaca fails")


@pytest.mark.parametrize("failure", [TimeoutError(), AlpacaUnavailable(), AlpacaRateLimited()])
async def test_balances_unavailable(failure) -> None:
    uow, alpaca, user = MemoryFactory(), FakeFunding(), uuid4()
    uow.link(user)
    alpaca.failure = failure
    service = WalletService(
        uow, alpaca, FakeClock(datetime(2026, 1, 1, tzinfo=UTC)), StatusWriter()
    )
    view = await service.get_balances(user)
    assert view.unavailable
    assert all(
        getattr(view, field) is None
        for field in (
            "cash",
            "cash_withdrawable",
            "buying_power",
            "equity",
            "portfolio_value",
            "long_market_value",
        )
    )
