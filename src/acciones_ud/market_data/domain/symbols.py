"""RF-24/16.4: instrument identifier used in paths and bodies."""

import re

from acciones_ud.shared.domain.errors import AppError, ErrorCode

SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9./-]+$")
MAX_SYMBOL_LENGTH = 20


def is_valid_symbol(value: str) -> bool:
    return 1 <= len(value) <= MAX_SYMBOL_LENGTH and SYMBOL_PATTERN.fullmatch(value) is not None


def validate_symbol(raw: str) -> str:
    value = raw.strip()
    if not is_valid_symbol(value):
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: symbol")
    return value.upper()
