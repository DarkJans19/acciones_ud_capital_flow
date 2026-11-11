"""RF-26: watchlist limits and name validation."""

from acciones_ud.shared.domain.errors import AppError, ErrorCode

WATCHLIST_LIMIT = 20
SYMBOL_LIMIT = 50
MAX_NAME_LENGTH = 100


def validate_name(raw: str) -> str:
    value = raw.strip()
    if not 1 <= len(value) <= MAX_NAME_LENGTH:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: name")
    return value


def ensure_can_create(existing: int) -> None:
    if existing >= WATCHLIST_LIMIT:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            f"A user cannot own more than {WATCHLIST_LIMIT} watchlists.",
        )


def ensure_can_add(symbols: list[str], symbol: str) -> None:
    if symbol in symbols:
        raise AppError(
            409,
            ErrorCode.SYMBOL_ALREADY_IN_WATCHLIST,
            "The symbol is already in the watchlist.",
        )
    if len(symbols) >= SYMBOL_LIMIT:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            f"A watchlist cannot hold more than {SYMBOL_LIMIT} symbols.",
        )
