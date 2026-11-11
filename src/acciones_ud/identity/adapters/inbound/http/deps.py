from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie

from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.infrastructure.cookies import ACCESS_COOKIE

access_cookie = APIKeyCookie(
    name=ACCESS_COOKIE,
    scheme_name="AccessTokenCookie",
    auto_error=False,
    description="JWT access token issued in the HttpOnly access_token cookie.",
)


async def authenticate_access_token(token: str, request: Request) -> CurrentUser:
    from acciones_ud.identity.composition import auth_context, token_codec

    claims = token_codec(request).decode(token)
    user = await auth_context(request, claims.user_id, claims.session_id)
    if user is None:
        raise AppError(401, ErrorCode.NOT_AUTHENTICATED, "Authentication required.")
    return user


async def get_current_user(
    request: Request, token: Annotated[str | None, Depends(access_cookie)]
) -> CurrentUser:
    if not token:
        raise AppError(401, ErrorCode.NOT_AUTHENTICATED, "Authentication required.")
    return await authenticate_access_token(token, request)


def require_permission(code: str) -> Callable[..., Awaitable[CurrentUser]]:
    async def check(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if user.account_status != "active" or code not in user.permissions:
            raise AppError(403, ErrorCode.FORBIDDEN, "Permission required.")
        return user

    return check


async def require_premium(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if not user.is_premium:
        raise AppError(403, ErrorCode.PREMIUM_REQUIRED, "Premium account required.")
    return user
