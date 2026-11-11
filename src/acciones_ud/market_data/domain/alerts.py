"""RF-26 / Property 24: price alert evaluation (pure)."""

from decimal import Decimal

from acciones_ud.market_data.domain.entities import AlertStatus, Comparator
from acciones_ud.shared.domain.errors import AppError, ErrorCode

MAX_THRESHOLD = Decimal("999999999.99")
COMPARATORS = tuple(item.value for item in Comparator)


def validate_threshold(value: Decimal) -> Decimal:
    if value <= 0 or value > MAX_THRESHOLD:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: threshold")
    return value


def should_trigger(
    comparator: Comparator,
    threshold: Decimal,
    previous: Decimal | None,
    current: Decimal,
) -> bool:
    if comparator is Comparator.ABOVE:
        return current >= threshold
    if comparator is Comparator.BELOW:
        return current <= threshold
    if current == threshold:
        return True
    if previous is None:
        return False
    return (previous < threshold <= current) or (previous > threshold >= current)


def evaluate(
    status: AlertStatus,
    comparator: Comparator,
    threshold: Decimal,
    previous: Decimal | None,
    current: Decimal | None,
) -> tuple[AlertStatus, Decimal | None, bool]:
    if status is not AlertStatus.ACTIVE:
        return status, previous, False
    if current is None:
        return status, previous, False
    if should_trigger(comparator, threshold, previous, current):
        return AlertStatus.TRIGGERED, current, True
    return AlertStatus.ACTIVE, current, False
