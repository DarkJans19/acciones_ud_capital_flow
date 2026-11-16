from dataclasses import dataclass, replace
from decimal import Decimal
from typing import cast

from acciones_ud.brokers.domain.errors import ValidationError


@dataclass(frozen=True)
class ProposalContent:
    symbol: str
    side: str
    qty: Decimal
    type: str
    limit_price: Decimal | None = None

    def validated(self) -> "ProposalContent":
        value = replace(self, symbol=self.symbol.strip().upper())
        if not 1 <= len(value.symbol) <= 32:
            raise ValidationError("symbol")
        if value.side not in {"buy", "sell"}:
            raise ValidationError("side")
        if (
            not value.qty.is_finite()
            or not 0 < value.qty < Decimal("1e11")
            or cast(int, value.qty.as_tuple().exponent) < -9
        ):
            raise ValidationError("qty")
        if value.type not in {"market", "limit"}:
            raise ValidationError("type")
        if value.type == "limit":
            price = value.limit_price
            if (
                price is None
                or not price.is_finite()
                or not 0 < price < Decimal("1e14")
                or cast(int, price.as_tuple().exponent) < -4
            ):
                raise ValidationError("limit_price")
        elif value.limit_price is not None:
            raise ValidationError("limit_price", "market_order")
        return value
