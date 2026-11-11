# Feature: identity-market-backend, Property 22: Symbol path validation

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.symbols import validate_symbol
from acciones_ud.shared.domain.errors import AppError

ALLOWED = set(string.ascii_letters + string.digits + "./-")


def reference(raw: str) -> str | None:
    value = raw.strip()
    if not 1 <= len(value) <= 20:
        return None
    if any(character not in ALLOWED for character in value):
        return None
    return value.upper()


@given(st.text(max_size=40))
def test_symbol_validation_matches_reference(raw: str) -> None:
    expected = reference(raw)
    if expected is None:
        with pytest.raises(AppError) as error:
            validate_symbol(raw)
        assert error.value.status == 422
    else:
        assert validate_symbol(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("aapl", "AAPL"),
        (" brk.b ", "BRK.B"),
        ("BRK/B", "BRK/B"),
        ("a-1", "A-1"),
    ],
)
def test_symbol_validation_accepts_canonical_forms(raw: str, expected: str) -> None:
    assert validate_symbol(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "A" * 21, "AAPL$", "AAP L", "ÁAPL"])
def test_symbol_validation_rejects_invalid_forms(raw: str) -> None:
    with pytest.raises(AppError):
        validate_symbol(raw)
