import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request, Response
from fastapi.routing import APIRoute

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user, require_permission
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.identity.domain.rbac import ADMIN_READ_ROLES
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class AuditRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def audited(request: Request) -> Response:
            try:
                return await handler(request)
            except AppError as exc:
                if exc.status in {401, 403}:
                    logging.getLogger(__name__).warning(
                        "Admin access rejected method=%s path=%s code=%s user=%s",
                        request.method,
                        self.path,
                        exc.code,
                        getattr(request.state, "admin_actor_id", None),
                        extra={"request_id": getattr(request.state, "request_id", None)},
                    )
                raise

        return audited


def capability(code: str) -> Callable[..., Awaitable[CurrentUser]]:
    async def check(
        request: Request, user: Annotated[CurrentUser, Depends(get_current_user)]
    ) -> CurrentUser:
        request.state.admin_actor_id = str(user.user_id)
        await require_permission(code)(user)
        roles = ADMIN_READ_ROLES.get(code, frozenset({"administrator"}))
        if not user.roles.intersection(roles):
            raise AppError(403, ErrorCode.FORBIDDEN, "Administrative role required.")
        return user

    return check


async def investor_or_broker(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if user.account_status != "active" or not user.roles.intersection({"investor", "broker"}):
        raise AppError(403, ErrorCode.FORBIDDEN, "Investor or broker role required.")
    return user


async def investor(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.account_status != "active" or "investor" not in user.roles:
        raise AppError(403, ErrorCode.FORBIDDEN, "Investor role required.")
    return user


FeesAdmin = Annotated[CurrentUser, Depends(capability("admin:fees"))]
CommissionsAdmin = Annotated[CurrentUser, Depends(capability("admin:commissions"))]
MarketsAdmin = Annotated[CurrentUser, Depends(capability("admin:markets"))]
HaltsAdmin = Annotated[CurrentUser, Depends(capability("admin:halts"))]
AuditReader = Annotated[CurrentUser, Depends(capability("admin:audit"))]
ComplianceAdmin = Annotated[CurrentUser, Depends(capability("admin:compliance"))]
ComplianceReader = Annotated[CurrentUser, Depends(capability("admin:compliance:read"))]
BiReader = Annotated[CurrentUser, Depends(capability("admin:bi"))]
Trader = Annotated[CurrentUser, Depends(investor_or_broker)]
Investor = Annotated[CurrentUser, Depends(investor)]
Authenticated = Annotated[CurrentUser, Depends(get_current_user)]
