from decimal import Decimal

import pytest
from pydantic import ValidationError

from acciones_ud.orders.adapters.inbound.http.schemas.orders import OrderIn, ResubmitIn


def test_decimal_inputs_are_strings_and_totp_is_not_in_domain() -> None:
    for value in [0.1, 1, float("nan")]:
        with pytest.raises(ValidationError):
            OrderIn(symbol="AAPL", side="buy", qty=value)
    body = OrderIn(symbol="AAPL", side="buy", qty="0.000000001", totp_code="123456")
    assert body.to_request().qty == Decimal("0.000000001")
    assert not hasattr(body.to_request(), "totp_code")
    assert "123456" not in repr(body)
    assert ResubmitIn(qty="1.5").changes() == {"qty": Decimal("1.5")}
