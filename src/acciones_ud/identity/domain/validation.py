import re
from collections.abc import Callable

import pycountry
from email_validator import EmailNotValidError, validate_email


def normalize_email(value: str) -> str:
    return value.strip().lower()


def valid_email(value: str) -> bool:
    try:
        validate_email(value.strip(), check_deliverability=False)
        return len(value.strip()) <= 254
    except EmailNotValidError:
        return False


def valid_name(value: str, maximum: int = 100) -> bool:
    return 1 <= len(value.strip()) <= maximum


def valid_phone(value: str) -> bool:
    return re.fullmatch(r"\+[1-9][0-9]{1,14}", value) is not None


def valid_country(value: str) -> bool:
    return len(value) == 2 and pycountry.countries.get(alpha_2=value.upper()) is not None


def valid_password(value: str) -> bool:
    return (
        8 <= len(value) <= 128
        and any(x.isalpha() for x in value)
        and any(x.isdigit() for x in value)
    )


def invalid_registration_fields(payload: dict[str, object], kind: str) -> list[str]:
    invalid: list[str] = []
    checks: dict[str, Callable[[str], bool]] = {
        "first_names": valid_name,
        "last_names": valid_name,
        "email": valid_email,
        "phone": valid_phone,
        "country": valid_country,
        "password": valid_password,
    }
    if kind == "broker":
        checks.update(
            firm_name=lambda v: valid_name(v, 200), license_number=lambda v: valid_name(v, 50)
        )
    for name, check in checks.items():
        value = payload.get(name)
        if not isinstance(value, str) or not check(value):
            invalid.append(name)
    if payload.get("terms_accepted") is not True:
        invalid.append("terms_accepted")
    for name in ("monthly_report", "broker_requested", "premium_requested"):
        if type(payload.get(name, None if name == "monthly_report" else False)) is not bool:
            invalid.append(name)
    interests = payload.get("interests", [])
    if (
        not isinstance(interests, list)
        or len(interests) > 20
        or any(not isinstance(x, str) or not 1 <= len(x) <= 50 for x in interests)
    ):
        invalid.append("interests")
    if payload.get("investor_level") not in (None, "beginner", "experienced"):
        invalid.append("investor_level")
    return invalid
