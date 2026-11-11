from typing import Annotated

from fastapi import APIRouter, Depends, Request

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user, require_permission
from acciones_ud.identity.adapters.inbound.http.schemas.preferences import InterestsIn
from acciones_ud.identity.adapters.inbound.http.schemas.users import UserMeOut
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/users/me", tags=["account"])


@router.get("", response_model=UserMeOut, responses=error_responses(401, 503))
async def me(request: Request, user: Annotated[CurrentUser, Depends(get_current_user)]) -> Record:
    from acciones_ud.identity.composition import account_info_service

    return await account_info_service(request).me(user)


@router.post("/mfa/recovery-codes", responses=error_responses(401, 409, 503))
async def regenerate_codes(
    request: Request, user: Annotated[CurrentUser, Depends(get_current_user)]
) -> dict[str, list[str]]:
    from acciones_ud.identity.composition import auth_service

    return {"recovery_codes": await auth_service(request).regenerate(user.user_id)}


@router.put("/interests", response_model=InterestsIn, responses=error_responses(401, 403, 422, 503))
async def interests(
    body: InterestsIn,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("account:manage"))],
) -> Record:
    from acciones_ud.identity.composition import account_service

    return await account_service(request).interests(user.user_id, body.interests, body.level)
