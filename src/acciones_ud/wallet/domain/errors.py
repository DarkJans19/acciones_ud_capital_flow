from decimal import Decimal

from acciones_ud.shared.domain.errors import AppError, ErrorCode


class InvalidAmountError(AppError):
    def __init__(self) -> None:
        super().__init__(
            422, ErrorCode.VALIDATION_ERROR, "Invalid field: amount", {"fields": ["amount"]}
        )


class InsufficientFundsError(AppError):
    def __init__(self, withdrawable: Decimal) -> None:
        super().__init__(
            422,
            ErrorCode.INSUFFICIENT_FUNDS,
            "Insufficient withdrawable funds.",
            {"cash_withdrawable": str(withdrawable)},
        )


class InvalidSignatureError(AppError):
    def __init__(self) -> None:
        super().__init__(400, ErrorCode.WEBHOOK_SIGNATURE_INVALID, "Invalid webhook signature.")


class StripeUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(502, ErrorCode.STRIPE_UNAVAILABLE, "Stripe is unavailable.")


class StripeRejectedError(StripeUnavailableError):
    """Stripe rejected the configured checkout or subscription operation."""
