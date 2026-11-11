from decimal import Decimal, InvalidOperation

from acciones_ud.shared.domain.errors import AppError, ErrorCode

PORTFOLIO_DEFAULTS: dict[str, object] = {
    "view_type": "table",
    "sort_by": "symbol",
    "sort_direction": "asc",
    "hide_threshold": Decimal("0.00"),
}
ORDER_DEFAULTS: dict[str, object] = {
    "default_order_type": "market",
    "daily_order_limit": 50,
    "high_order_threshold_usd": Decimal("10000.00"),
    "extra_confirmation": True,
}


def money(value: object, *, positive: bool = False) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = Decimal(str(value))
        exponent = number.as_tuple().exponent
        return (
            number.is_finite()
            and number <= Decimal("999999999.99")
            and (number > 0 if positive else number >= 0)
            and isinstance(exponent, int)
            and exponent >= -2
        )
    except (InvalidOperation, ValueError, TypeError):
        return False


def validate_settings(kind: str, values: dict[str, object]) -> None:
    if kind == "portfolio":
        checks = {
            "view_type": values.get("view_type") in ("table", "cards", "chart"),
            "sort_by": values.get("sort_by")
            in ("symbol", "market_value", "gain_loss", "allocation"),
            "sort_direction": values.get("sort_direction") in ("asc", "desc"),
            "hide_threshold": money(values.get("hide_threshold")),
        }
    else:
        limit = values.get("daily_order_limit")
        checks = {
            "default_order_type": values.get("default_order_type")
            in ("market", "limit", "stop", "stop_limit", "trailing_stop"),
            "daily_order_limit": type(limit) is int
            and isinstance(limit, int)
            and 1 <= limit <= 1000,
            "high_order_threshold_usd": money(
                values.get("high_order_threshold_usd"), positive=True
            ),
            "extra_confirmation": type(values.get("extra_confirmation")) is bool,
        }
    invalid = [name for name, valid in checks.items() if not valid]
    if invalid:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Invalid settings fields.",
            {"errors": [{"field": n, "issue": "invalid"} for n in invalid]},
        )
