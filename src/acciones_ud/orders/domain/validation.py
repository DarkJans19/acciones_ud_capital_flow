from decimal import Decimal

from acciones_ud.orders.domain.model import FieldError, OrderRequest, TradableAsset

TYPES = frozenset({"market", "limit", "stop", "stop_limit", "trailing_stop"})


def allows_fraction(asset: TradableAsset, order_class: str, order_type: str, tif: str) -> bool:
    return (
        asset.fractionable
        and order_class == "simple"
        and order_type in {"market", "limit", "stop", "stop_limit"}
        and tif == "day"
    )


def valid_price(value: Decimal) -> bool:
    if not value.is_finite() or value <= 0:
        return False
    exponent = value.as_tuple().exponent
    return isinstance(exponent, int) and exponent >= (-2 if value >= 1 else -4)


def validate(request: OrderRequest, asset: TradableAsset, base_price: Decimal) -> list[FieldError]:
    invalid: set[str] = set()
    if request.side not in {"buy", "sell"}:
        invalid.add("side")
    if request.type not in TYPES:
        invalid.add("type")
    if request.order_class not in {"simple", "bracket"}:
        invalid.add("order_class")
    if request.time_in_force not in {"day", "gtc", "ioc", "fok"}:
        invalid.add("time_in_force")
    qty = request.qty
    if not qty.is_finite() or qty <= 0:
        invalid.add("qty")
    else:
        exponent = qty.as_tuple().exponent
        if not isinstance(exponent, int) or exponent < -9:
            invalid.add("qty")
        if qty != qty.to_integral_value() and not allows_fraction(
            asset, request.order_class, request.type or "", request.time_in_force
        ):
            invalid.add("qty")
    prices = {
        "limit_price": request.limit_price,
        "stop_price": request.stop_price,
        "trail_price": request.trail_price,
        "trail_percent": request.trail_percent,
    }
    required = {
        "limit": {"limit_price"},
        "stop": {"stop_price"},
        "stop_limit": {"limit_price", "stop_price"},
    }.get(request.type or "", set())
    allowed = {"trail_price", "trail_percent"} if request.type == "trailing_stop" else required
    for name, value in prices.items():
        if name in required and value is None or name not in allowed and value is not None:
            invalid.add(name)
        if value is not None:
            if name == "trail_percent":
                if not value.is_finite() or not Decimal("0.1") <= value <= Decimal("50.0"):
                    invalid.add(name)
            elif not valid_price(value):
                invalid.add(name)
    if request.type == "trailing_stop" and (
        (request.trail_price is None) == (request.trail_percent is None)
    ):
        invalid.update({"trail_price", "trail_percent"})
    if (request.type == "trailing_stop" or request.order_class == "bracket") and (
        request.time_in_force not in {"day", "gtc"}
    ):
        invalid.add("time_in_force")
    legs = {
        "take_profit.limit_price": request.take_profit_limit_price,
        "stop_loss.stop_price": request.stop_loss_stop_price,
    }
    if request.order_class == "bracket":
        if request.side != "buy":
            invalid.add("side")
        if request.type not in {"market", "limit"}:
            invalid.add("type")
        if qty.is_finite() and qty != qty.to_integral_value():
            invalid.add("qty")
        for name, value in legs.items():
            if value is None or not valid_price(value):
                invalid.add(name)
            elif base_price.is_finite() and (
                name == "take_profit.limit_price"
                and value < base_price + Decimal("0.01")
                or name == "stop_loss.stop_price"
                and value > base_price - Decimal("0.01")
            ):
                invalid.add(name)
    else:
        invalid.update(name for name, value in legs.items() if value is not None)
    return [FieldError(name) for name in sorted(invalid)]
