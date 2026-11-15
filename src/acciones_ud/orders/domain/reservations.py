from decimal import Decimal
from typing import Literal

from acciones_ud.orders.domain.errors import (
    InsufficientBuyingPowerError,
    InsufficientPositionError,
    InvalidTransitionError,
)


def check_buy(
    estimated: Decimal, buying_power: Decimal, active_usd: Decimal, own: Decimal = Decimal(0)
) -> None:
    available = buying_power - active_usd + own
    if estimated > available:
        raise InsufficientBuyingPowerError(estimated, available)


def check_sell(
    qty: Decimal, qty_available: Decimal, reserved_shares: Decimal, own: Decimal = Decimal(0)
) -> None:
    if qty_available <= 0 or qty > qty_available - reserved_shares + own:
        raise InsufficientPositionError()


def next_state(
    current: str, target: Literal["active", "transferred", "released"]
) -> Literal["active", "transferred", "released"]:
    if current != target and current in {"transferred", "released"}:
        raise InvalidTransitionError()
    if target not in {"active", "transferred", "released"}:
        raise InvalidTransitionError()
    return target
