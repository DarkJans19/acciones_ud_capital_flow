from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import APIKeyCookie

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.adapters.inbound.http.schemas.sessions import (
    RefreshOut,
    RevokedCountOut,
    SessionOut,
)
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.infrastructure.cookies import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
)
from acciones_ud.shared.infrastructure.http_errors import error_body_response, error_responses

router = APIRouter(tags=["sessions"])
User = Annotated[CurrentUser, Depends(get_current_user)]
access_cookie = APIKeyCookie(
    name=ACCESS_COOKIE, scheme_name="AccessTokenCookie", auto_error=False
)
refresh_cookie = APIKeyCookie(
    name=REFRESH_COOKIE, scheme_name="RefreshTokenCookie", auto_error=False
)


@router.post("/auth/refresh", response_model=RefreshOut, responses=error_responses(401, 503))
async def refresh(
    request: Request, response: Response, token: Annotated[str | None, Depends(refresh_cookie)]
) -> Record:
    from acciones_ud.identity.composition import session_service

    result = await session_service(request).refresh(token)
    set_auth_cookies(
        response, result.pop("access"), result.pop("refresh"), request.app.state.settings
    )
    return result


@router.post("/auth/logout", status_code=204, responses=error_responses(503))
async def logout(
    request: Request,
    access_token: Annotated[str | None, Depends(access_cookie)],
    refresh_token: Annotated[str | None, Depends(refresh_cookie)],
) -> Response:
    from acciones_ud.identity.composition import session_service

    try:
        await session_service(request).logout(access_token, refresh_token)
    except AppError as exc:
        if exc.code is not ErrorCode.DATABASE_UNAVAILABLE:
            raise
        response: Response = error_body_response(exc)
        clear_auth_cookies(response, request.app.state.settings)
        return response
    response = Response(status_code=204)
    clear_auth_cookies(response, request.app.state.settings)
    return response


@router.get(
    "/users/me/sessions", response_model=list[SessionOut], responses=error_responses(401, 503)
)
async def list_sessions(request: Request, user: User) -> list[Record]:
    from acciones_ud.identity.composition import session_service

    return await session_service(request).list(user)


@router.delete(
    "/users/me/sessions/{session_id}",
    status_code=204,
    responses=error_responses(401, 404, 422, 503),
)
async def close_session(session_id: UUID, request: Request, user: User) -> Response:
    from acciones_ud.identity.composition import session_service

    await session_service(request).close(user, session_id)
    response = Response(status_code=204)
    if session_id == user.session_id:
        clear_auth_cookies(response, request.app.state.settings)
    return response


@router.post(
    "/users/me/sessions/revoke-others",
    response_model=RevokedCountOut,
    responses=error_responses(401, 503),
)
async def revoke_others(request: Request, user: User) -> dict[str, int]:
    from acciones_ud.identity.composition import session_service

    return {"revoked_count": await session_service(request).close_others(user)}
