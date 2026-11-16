from typing import Literal, Protocol

from acciones_ud.shared.domain.errors import AppError, ErrorCode


class AuthenticatedUser(Protocol):
    @property
    def roles(self) -> frozenset[str]: ...
    @property
    def account_status(self) -> str: ...


def resolve(user: AuthenticatedUser, required: Literal["investor", "broker"]) -> None:
    if user.account_status != "active" or required not in user.roles:
        raise AppError(403, ErrorCode.FORBIDDEN, "Required role is not active.")
