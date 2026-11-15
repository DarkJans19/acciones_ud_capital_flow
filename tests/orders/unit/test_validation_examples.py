from dataclasses import replace
from decimal import Decimal

from acciones_ud.orders.domain.model import OrderRequest, TradableAsset
from acciones_ud.orders.domain.validation import validate


def test_collects_invalid_fields() -> None:
    asset = TradableAsset("AAPL", "NASDAQ", True, True, True)
    request = OrderRequest("AAPL", "buy", Decimal("1"), type="market")
    assert validate(request, asset, Decimal("100")) == []
    errors = validate(
        replace(request, qty=Decimal("NaN"), side="invalid", limit_price=Decimal("0")),
        asset,
        Decimal("100"),
    )
    assert {e.field for e in errors} == {"qty", "side", "limit_price"}
