from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from acciones_ud.orders.adapters.outbound.brokers.null_broker_link import NullBrokerLink
from acciones_ud.orders.adapters.outbound.wallet.buying_power import WalletBuyingPowerAdapter
from acciones_ud.shared.domain.errors import AppError


async def test_buying_power_and_null_broker_contract() -> None:
    funding = SimpleNamespace(
        get_trading_account=AsyncMock(return_value={"buying_power": "1.2345"})
    )
    adapter = WalletBuyingPowerAdapter(funding)
    assert await adapter.buying_power("account") == Decimal("1.2345")
    funding.get_trading_account.assert_awaited_with("account", timeout_s=4)
    funding.get_trading_account.return_value = {"buying_power": "NaN"}
    with pytest.raises(AppError) as caught:
        await adapter.buying_power("account")
    assert caught.value.status == 502
    broker = NullBrokerLink()
    assert await broker.reviewing_broker(uuid4()) is None
    assert not await broker.is_linked(uuid4(), uuid4())
    assert await broker.linked_investors(uuid4()) == []
