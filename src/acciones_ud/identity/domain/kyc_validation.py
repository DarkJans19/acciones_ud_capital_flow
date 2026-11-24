"""RFP-01: local checks before reserving or submitting a financial identity."""

import re
from datetime import date
from typing import Literal, get_args

from acciones_ud.shared.domain.errors import AppError, ErrorCode

TaxIdType = Literal[
    "USA_SSN",
    "USA_ITIN",
    "COL_NIT",
    "PASSPORT",
    "NATIONAL_ID",
    "PERMANENT_RESIDENT",
    "DRIVER_LICENSE",
    "OTHER_GOV_ID",
]
SUPPORTED_TAX_ID_TYPES = frozenset(get_args(TaxIdType))


def invalid(field: str, issue: str) -> AppError:
    # Never include an identifier or birth date in the error.
    return AppError(
        422,
        ErrorCode.VALIDATION_ERROR,
        f"Invalid field: {field}",
        {"errors": [{"field": f"identity.{field}", "issue": issue}]},
    )


def validate_adult(birthday: date, today: date) -> None:
    age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    if birthday > today or age < 18:
        raise invalid("date_of_birth", "Must be at least 18 completed years old")


def validate_tax_id(value: object, kind: object, tax_country: object) -> None:
    if not isinstance(kind, str) or kind not in SUPPORTED_TAX_ID_TYPES:
        raise invalid("tax_id_type", "Unsupported document type")
    # Alpaca Data Validations: common transport rules, not a passport-country pattern.
    if (
        not isinstance(value, str)
        or not 2 <= len(value) <= 40
        or re.fullmatch(r"[A-Za-z0-9.+-]+", value) is None
        or re.search(r"[0-9]", value) is None
    ):
        raise invalid("tax_id", "Invalid identifier format")
    digits = re.sub(r"[^0-9]", "", value)
    steps = [int(right) - int(left) for left, right in zip(digits, digits[1:], strict=False)]
    if value.replace("-", "").replace(".", "").isdigit() and (
        len(set(digits)) == 1
        or all(step == 1 for step in steps)
        or all(step == -1 for step in steps)
    ):
        raise invalid("tax_id", "Placeholder identifier is not allowed")
    if kind in {"USA_SSN", "USA_ITIN"}:
        if tax_country != "USA":
            raise invalid("tax_id_type", "Document type requires USA tax residence")
        if re.fullmatch(r"(?:[0-9]{9}|[0-9]{3}-[0-9]{2}-[0-9]{4})", value) is None:
            raise invalid("tax_id", "Expected nine digits, optionally formatted XXX-XX-XXXX")
        if digits[:3] in {"000", "666"} or digits[3:5] == "00" or digits[5:] == "0000":
            raise invalid("tax_id", "Invalid area, group or serial")
    elif kind == "COL_NIT":
        if tax_country != "COL":
            raise invalid("tax_id_type", "Document type requires COL tax residence")
        # Lexical NIT validation only: numeric base, optional thousands separators / DV.
        # Do not invent a fixed base length or claim to verify DIAN's registration.
        if re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)(?:-[0-9])?", value) is None:
            raise invalid("tax_id", "Expected a numeric NIT with optional verification digit")
    # Generic government IDs retain spelling and punctuation. Eligibility and
    # country-specific patterns remain subject to Alpaca/correspondent verification.
