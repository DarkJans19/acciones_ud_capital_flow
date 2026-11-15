from acciones_ud.orders.domain.errors import InvalidTransitionError
from acciones_ud.orders.domain.model import OrderStatus as S

ALLOWED: dict[S, frozenset[S]] = {
    S.PENDING: frozenset(
        {S.IN_REVIEW, S.SUBMITTED, S.HELD, S.CANCELED, S.REJECTED, S.EXPIRED, S.FAILED}
    ),
    S.IN_REVIEW: frozenset({S.PENDING, S.BROKER_SIGNED, S.CANCELED, S.EXPIRED}),
    S.BROKER_SIGNED: frozenset(
        {S.IN_REVIEW, S.SUBMITTED, S.HELD, S.CANCELED, S.REJECTED, S.EXPIRED, S.FAILED}
    ),
    S.HELD: frozenset(
        {
            S.PENDING,
            S.BROKER_SIGNED,
            S.IN_REVIEW,
            S.SUBMITTED,
            S.CANCELED,
            S.REJECTED,
            S.EXPIRED,
            S.FAILED,
        }
    ),
    S.SUBMITTED: frozenset({S.EXECUTING, S.CANCELED, S.REJECTED, S.EXPIRED, S.FAILED}),
    S.EXECUTING: frozenset({S.EXECUTING, S.CANCELED, S.EXPIRED}),
    S.CANCELED: frozenset(),
    S.REJECTED: frozenset(),
    S.EXPIRED: frozenset(),
    S.FAILED: frozenset(),
}


def is_terminal(status: S, fully_filled: bool) -> bool:
    return status in {S.CANCELED, S.REJECTED, S.EXPIRED, S.FAILED} or (
        status == S.EXECUTING and fully_filled
    )


def transition(current: S, target: S, fully_filled: bool) -> S:
    if is_terminal(current, fully_filled) or target not in ALLOWED.get(current, frozenset()):
        raise InvalidTransitionError()
    return target
