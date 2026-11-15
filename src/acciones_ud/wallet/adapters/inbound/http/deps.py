from typing import Annotated

from fastapi import Depends

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.errors import AppError, ErrorCode


async def require_investor(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    # CurrentUser.roles contains the current assignments resolved by identity.
    if user.account_status != "active" or "investor" not in user.roles:
        raise AppError(403, ErrorCode.FORBIDDEN, "Investor role required.")
    return user
