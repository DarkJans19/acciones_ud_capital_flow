from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from acciones_ud.wallet.adapters.outbound.alpaca.fake_funding import FakeFunding
from acciones_ud.wallet.application.funding_service import FundingService
from acciones_ud.wallet.domain.model import BankRelationshipInput
from tests.support.clock import FakeClock
from tests.wallet.fakes import MemoryFactory


async def funding_setup():
    uow, alpaca, user_id = MemoryFactory(), FakeFunding(), uuid4()
    uow.link(user_id)
    alpaca.accounts["account"] = {
        "status": "ACTIVE",
        "currency": "USD",
        "cash_withdrawable": "1000.00",
        "buying_power": "1000.00",
        "cash": "1000.00",
        "equity": "1000.00",
        "portfolio_value": "1000.00",
        "long_market_value": "0.00",
    }
    clock = FakeClock(datetime(2026, 11, 13, 15, tzinfo=UTC))
    service = FundingService(uow, alpaca, clock, Decimal("50000.00"))
    bank = await service.create_bank_relationship(
        user_id, BankRelationshipInput("Sandbox Investor", "CHECKING", "1234567890", "123456789")
    )
    return service, uow, alpaca, user_id, bank, clock
