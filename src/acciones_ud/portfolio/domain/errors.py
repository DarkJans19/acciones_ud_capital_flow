from acciones_ud.shared.domain.errors import AppError, ErrorCode


class InvalidPeriodError(AppError):
    def __init__(self, field: str, reason: str) -> None:
        self.field, self.reason = field, reason
        super().__init__(
            422, ErrorCode.INVALID_PERIOD, "Invalid period.", {"field": field, "reason": reason}
        )


class AccountNotLinkedError(AppError):
    def __init__(self) -> None:
        super().__init__(409, ErrorCode.ACCOUNT_NOT_LINKED, "Linked account required.")


class NotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(404, ErrorCode.NOT_FOUND, "Resource not found.")
