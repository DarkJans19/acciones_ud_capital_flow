from datetime import timedelta

import pytest

from acciones_ud.shared.domain.errors import AppError
from acciones_ud.wallet.application.wallet_service import WalletService
from acciones_ud.wallet.domain.model import Activity
from tests.wallet.support import funding_setup
from tests.wallet.unit.test_balances import StatusWriter


async def test_currencies_activities_and_period() -> None:
    _, uow, alpaca, user, _, clock = await funding_setup()
    service = WalletService(uow, alpaca, clock, StatusWriter())
    alpaca.accounts["account"].pop("currency")
    assert await service.get_currencies(user) == {
        "currencies": ["USD"],
        "conversion_supported": False,
    }
    alpaca.activities["account"] = [
        Activity("conversion", "FX", clock.now()),
        Activity("fill", "FILL", clock.now()),
    ]
    page = await service.list_activities(user)
    assert [item.id for item in page.items] == ["fill"]
    with pytest.raises(AppError) as caught:
        await service.list_activities(user, clock.now(), clock.now() - timedelta(days=1))
    assert caught.value.status == 422
