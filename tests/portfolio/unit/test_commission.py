from decimal import Decimal as D
from uuid import uuid4

from acciones_ud.portfolio.adapters.outbound.brokers.null_broker_client import NullBrokerClient
from acciones_ud.portfolio.adapters.outbound.commissions.reference_commission import (
    ReferenceCommission,
)
from tests.portfolio.property.test_pnl import records


async def test_default_ports():
    execution = records([("sell", D("0.123456789"), D("13.4321"))])[0]
    quote = ReferenceCommission().commission(execution)
    assert quote.amount == execution.qty * execution.price * D(".02")
    assert quote.source == "reference"
    port = NullBrokerClient()
    assert await port.linked_investors(uuid4()) == []
    assert not await port.is_linked(uuid4(), uuid4())
