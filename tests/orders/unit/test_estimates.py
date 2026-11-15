from dataclasses import replace
from decimal import Decimal as D

from acciones_ud.orders.domain.estimates import estimated_amount, requires_extra_authorization
from acciones_ud.orders.domain.idempotency import request_hash
from acciones_ud.orders.domain.model import OrderControls, OrderRequest


def test_rounding_threshold_and_canonical_hash() -> None:
    assert estimated_amount("buy", D("0.1"), D("1.01"), D("0.02")) == D("0.11")
    controls = OrderControls(high_order_threshold_usd=D("10"))
    assert requires_extra_authorization(D("10"), controls) == "none"
    assert requires_extra_authorization(D("10.01"), controls) == "totp"
    request = OrderRequest("AAPL", "buy", D("10"), "market")
    assert request_hash(request) == request_hash(replace(request, qty=D("10.0")))
