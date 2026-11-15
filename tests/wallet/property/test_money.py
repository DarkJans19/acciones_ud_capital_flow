import re
from decimal import Decimal, InvalidOperation

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.shared.domain.errors import AppError
from acciones_ud.wallet.domain.money import exact_amount, parse_transfer_amount, validate_currency


# Feature: wallet-mod-04, Property 1: Validación de importe y moneda de transferencias
@settings(max_examples=100)
@given(
    st.one_of(st.text(), st.decimals(allow_nan=False, allow_infinity=False).map(str)),
    st.sampled_from(["USD", "COP", "EUR"]),
    st.integers(1, 100000),
)
def test_amount_reference(raw: str, currency: str, maximum: int) -> None:
    valid = bool(re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", raw)) and currency == "USD"
    try:
        valid = valid and 1 <= Decimal(raw) <= maximum
    except InvalidOperation:
        valid = False
    try:
        validate_currency(currency)
        result = parse_transfer_amount(raw, Decimal(maximum))
    except AppError:
        assert not valid
    else:
        assert valid and result == Decimal(raw)


# Feature: wallet-mod-04, Property 2: Importes de saldo exactos
@settings(max_examples=100)
@given(st.decimals(allow_nan=False, allow_infinity=False, places=9).map(str))
def test_exact_amount(raw: str) -> None:
    assert exact_amount(raw) == raw
    assert Decimal(exact_amount(raw)) == Decimal(raw)
