from enum import StrEnum


class DomainError(Exception):
    """Error esperado producido por una regla de dominio."""


class NotFoundError(DomainError):
    """El recurso solicitado no existe."""


class ErrorCode(StrEnum):
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    MFA_FAILED = "MFA_FAILED"
    REFRESH_INVALID = "REFRESH_INVALID"
    FORBIDDEN = "FORBIDDEN"
    PREMIUM_REQUIRED = "PREMIUM_REQUIRED"
    NOT_FOUND = "NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    LAST_ADMINISTRATOR = "LAST_ADMINISTRATOR"
    ASSIGNMENT_CANCELLED = "ASSIGNMENT_CANCELLED"
    BROKER_NOT_PENDING = "BROKER_NOT_PENDING"
    MFA_NOT_ENROLLED = "MFA_NOT_ENROLLED"
    KYC_ACCOUNT_EXISTS = "KYC_ACCOUNT_EXISTS"
    SYMBOL_ALREADY_IN_WATCHLIST = "SYMBOL_ALREADY_IN_WATCHLIST"
    OVERRIDE_EXISTS = "OVERRIDE_EXISTS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CHANNEL_NOT_AVAILABLE = "CHANNEL_NOT_AVAILABLE"
    ALPACA_REJECTED = "ALPACA_REJECTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ALPACA_UNAVAILABLE = "ALPACA_UNAVAILABLE"
    ALPACA_RATE_LIMITED = "ALPACA_RATE_LIMITED"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HTTP_ERROR = "HTTP_ERROR"


class AppError(DomainError):
    def __init__(
        self,
        status: int,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
