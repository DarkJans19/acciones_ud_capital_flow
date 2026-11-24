from acciones_ud.shared.domain.errors import AppError, ErrorCode


def invalid(field: str, reason: str = "invalid") -> AppError:
    return AppError(
        422,
        ErrorCode.VALIDATION_ERROR,
        "Invalid administrative field.",
        {"field": field, "reason": reason},
    )


def not_found(resource: str) -> AppError:
    return AppError(404, ErrorCode.NOT_FOUND, "Resource not found.", {"resource": resource})


def conflict(code: ErrorCode, **details: object) -> AppError:
    return AppError(409, code, "Administrative operation conflicts with stored state.", details)
