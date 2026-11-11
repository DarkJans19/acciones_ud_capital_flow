from acciones_ud.identity.domain.validation import invalid_registration_fields, normalize_email
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def build_new_user(kind: str, payload: dict[str, object]) -> tuple[dict[str, object], str | None]:
    invalid = invalid_registration_fields(payload, kind)
    if invalid:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Invalid registration fields.",
            {"errors": [{"field": x, "issue": "invalid"} for x in invalid]},
        )
    if kind not in {"investor", "broker", "administrator"}:
        raise ValueError("Unknown registration kind")
    result = {
        key: payload[key]
        for key in ("first_names", "last_names", "email", "phone", "country", "monthly_report")
    }
    for name in ("first_names", "last_names", "email"):
        result[name] = str(result[name]).strip()
    result["country"] = str(result["country"]).upper()
    result["email_normalized"] = normalize_email(str(result["email"]))
    result["interests"] = payload.get("interests", [])
    result["investor_level"] = payload.get("investor_level")
    for name in ("broker_requested", "premium_requested"):
        result[name] = payload.get(name, False)
    result["account_status"] = "pending_broker_activation" if kind == "broker" else "active"
    for name in ("firm_name", "license_number"):
        result[name] = str(payload[name]).strip() if kind == "broker" else None
    return result, None if kind == "broker" else kind
