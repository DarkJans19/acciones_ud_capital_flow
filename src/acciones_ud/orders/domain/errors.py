from decimal import Decimal

from acciones_ud.shared.domain.errors import AppError, ErrorCode


class OrderDomainError(AppError):
    """Expected, safe order failure translated at the HTTP boundary."""


class InvalidTransitionError(OrderDomainError):
    def __init__(self) -> None:
        super().__init__(409, ErrorCode.INVALID_ORDER_STATE, "Invalid order state.")


class InsufficientBuyingPowerError(OrderDomainError):
    def __init__(self, estimated: Decimal, available: Decimal) -> None:
        super().__init__(
            409,
            ErrorCode.INSUFFICIENT_BUYING_POWER,
            "Insufficient buying power.",
            {"estimated_amount": str(estimated), "available_buying_power": str(available)},
        )


class InsufficientPositionError(OrderDomainError):
    def __init__(self) -> None:
        super().__init__(409, ErrorCode.INSUFFICIENT_POSITION, "Insufficient available shares.")


class OrderSubmissionNotReceived(OrderDomainError):
    def __init__(self, *, rate_limited: bool = False) -> None:
        code = ErrorCode.ALPACA_RATE_LIMITED if rate_limited else ErrorCode.ALPACA_UNAVAILABLE
        super().__init__(503 if rate_limited else 502, code, "Alpaca did not receive the order.")


class OrderSubmissionUnknown(Exception):
    def __init__(self, *, server_error: bool = False) -> None:
        self.server_error = server_error


class AlpacaRejectedError(OrderDomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            422, ErrorCode.ORDER_REJECTED, "Alpaca rejected the order.", {"reason": reason[:300]}
        )


def not_found() -> OrderDomainError:
    return OrderDomainError(404, ErrorCode.ORDER_NOT_FOUND, "Order not found.")
