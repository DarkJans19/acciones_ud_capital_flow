import re
from decimal import Decimal, InvalidOperation

from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.wallet.domain.errors import InvalidAmountError


def parse_transfer_amount(raw: str, maximum: Decimal) -> Decimal:
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", raw):
        raise InvalidAmountError()
    try:
        amount = Decimal(raw)
        if not amount.is_finite() or not 1 <= amount <= maximum:
            raise InvalidAmountError()
    except InvalidOperation:
        raise InvalidAmountError() from None
    return amount


def validate_currency(currency: str) -> None:
    if currency != "USD":
        raise AppError(
            422, ErrorCode.CURRENCY_NOT_SUPPORTED, "Unsupported currency.", {"supported": ["USD"]}
        )


def exact_amount(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        if not Decimal(raw).is_finite():
            raise InvalidAmountError()
    except InvalidOperation:
        raise InvalidAmountError() from None
    return raw
