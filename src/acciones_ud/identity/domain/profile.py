"""Personal data editable before financial identity submission (RF-06, RFP-01)."""

from collections.abc import Callable

from acciones_ud.identity.domain.validation import valid_country, valid_name, valid_phone
from acciones_ud.shared.domain.errors import AppError, ErrorCode

PROFILE_FIELDS = ("first_names", "last_names", "phone", "country")


def normalize_profile_patch(values: dict[str, object]) -> dict[str, str]:
    checks: dict[str, Callable[[str], bool]] = {
        "first_names": valid_name,
        "last_names": valid_name,
        "phone": valid_phone,
        "country": valid_country,
    }
    errors: list[dict[str, str]] = []
    normalized: dict[str, str] = {}
    for field, value in values.items():
        if field not in checks:
            errors.append({"field": field, "issue": "Field is not editable"})
        elif not isinstance(value, str) or not checks[field](value):
            errors.append({"field": field, "issue": "Invalid or null value"})
        else:
            normalized[field] = (
                value.strip()
                if field in {"first_names", "last_names"}
                else value.upper()
                if field == "country"
                else value
            )
    if not values:
        errors.append({"field": "body", "issue": "At least one personal field is required"})
    if errors:
        raise AppError(
            422, ErrorCode.VALIDATION_ERROR, "Invalid profile fields.", {"errors": errors}
        )
    return normalized
