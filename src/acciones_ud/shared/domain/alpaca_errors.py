from acciones_ud.shared.domain.errors import AppError, ErrorCode


class AlpacaError(Exception):
    pass


class AlpacaUnavailable(AlpacaError):
    pass


class AlpacaRateLimited(AlpacaError):
    pass


class AlpacaValidationError(AlpacaError):
    pass


class AlpacaNotFound(AlpacaError):
    pass


class AlpacaAuthError(AlpacaError):
    pass


def classify(outcome: int | Exception) -> AlpacaError:
    if isinstance(outcome, Exception):
        return AlpacaUnavailable()
    if outcome == 429:
        return AlpacaRateLimited()
    if outcome in {401, 403}:
        return AlpacaAuthError()
    if outcome == 404:
        return AlpacaNotFound()
    if outcome in {400, 409, 422}:
        return AlpacaValidationError("Alpaca rejected the submitted data.")
    return AlpacaUnavailable()


def to_app_error(exc: AlpacaError) -> AppError:
    if isinstance(exc, AlpacaRateLimited):
        return AppError(503, ErrorCode.ALPACA_RATE_LIMITED, "Alpaca rate limit reached.")
    if isinstance(exc, AlpacaNotFound):
        return AppError(404, ErrorCode.SYMBOL_NOT_FOUND, "Symbol not found.")
    if isinstance(exc, AlpacaValidationError):
        return AppError(422, ErrorCode.ALPACA_REJECTED, "Alpaca rejected the submitted data.")
    if isinstance(exc, AlpacaAuthError):
        return AppError(500, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred.")
    return AppError(502, ErrorCode.ALPACA_UNAVAILABLE, "Alpaca is unavailable.")
