from acciones_ud.shared.domain.errors import AppError, ErrorCode


class BrokerNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(404, ErrorCode.BROKER_NOT_FOUND, "Broker not found.")


class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        code = {
            "link": ErrorCode.LINK_NOT_FOUND,
            "proposal": ErrorCode.PROPOSAL_NOT_FOUND,
            "client": ErrorCode.CLIENT_NOT_FOUND,
        }[resource]
        super().__init__(404, code, "Resource not found.")


class ConsentRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(422, ErrorCode.CONSENT_REQUIRED, "Consent required.")


class ConfirmationRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(422, ErrorCode.CONFIRMATION_REQUIRED, "Confirmation required.")


class ValidationError(AppError):
    def __init__(self, field: str, reason: str = "invalid") -> None:
        super().__init__(
            422, ErrorCode.VALIDATION_ERROR, "Invalid field.", {"field": field, "reason": reason}
        )


class InvalidPeriodError(ValidationError):
    def __init__(self) -> None:
        super().__init__("from", "after_to")


class LinkAlreadyExistsError(AppError):
    def __init__(self) -> None:
        super().__init__(409, ErrorCode.LINK_ALREADY_EXISTS, "An open link already exists.")


class InvalidLinkStateError(AppError):
    def __init__(self, current: str, reason: str | None = None) -> None:
        details: dict[str, object] = {"current_status": current}
        if reason:
            details["reason"] = reason
        super().__init__(409, ErrorCode.INVALID_LINK_STATE, "Invalid link state.", details)


class InvalidProposalStateError(AppError):
    def __init__(self, current: str) -> None:
        super().__init__(
            409,
            ErrorCode.INVALID_PROPOSAL_STATE,
            "Invalid proposal state.",
            {"current_status": current},
        )


class ProposalVersionConflictError(AppError):
    def __init__(self, current: int) -> None:
        super().__init__(
            409,
            ErrorCode.PROPOSAL_VERSION_CONFLICT,
            "Proposal version changed.",
            {"current_version": current},
        )


class TradingAuthorizationRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            409, ErrorCode.TRADING_AUTHORIZATION_REQUIRED, "Trading authorization required."
        )


class RatingNotAllowedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            409, ErrorCode.RATING_NOT_ALLOWED, "Rating requires a past or active link."
        )


class AccountNotLinkedError(AppError):
    def __init__(self) -> None:
        super().__init__(409, ErrorCode.ACCOUNT_NOT_LINKED, "Linked account required.")


class ExtraAuthorizationInvalidError(AppError):
    def __init__(self) -> None:
        super().__init__(401, ErrorCode.EXTRA_AUTHORIZATION_INVALID, "Extra authorization invalid.")


class QuoteUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(503, ErrorCode.QUOTE_UNAVAILABLE, "Quote unavailable.")


class AssetNotTradableError(AppError):
    def __init__(self) -> None:
        super().__init__(422, ErrorCode.ASSET_NOT_TRADABLE, "Asset not tradable.")
