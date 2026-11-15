from decimal import Decimal

from acciones_ud.wallet.domain.errors import InsufficientFundsError
from acciones_ud.wallet.domain.model import TransferState, TransferUpdate

TERMINAL = frozenset({"COMPLETE", "CANCELED", "RETURNED", "REJECTED"})


def check_withdrawable(amount: Decimal, cash_withdrawable: Decimal) -> None:
    if amount > cash_withdrawable:
        raise InsufficientFundsError(cash_withdrawable)


def decide_update(stored: TransferState, incoming: TransferUpdate) -> TransferState | None:
    if stored.status in TERMINAL:
        return None
    if stored.alpaca_updated_at is not None and incoming.updated_at <= stored.alpaca_updated_at:
        return None
    return TransferState(incoming.status, incoming.updated_at)
