from uuid import UUID

from fastapi import APIRouter, Request

from acciones_ud.admin.adapters.inbound.http import schemas as s
from acciones_ud.admin.adapters.inbound.http.commissions_router import Size
from acciones_ud.admin.adapters.inbound.http.deps import AuditRoute, Authenticated, HaltsAdmin
from acciones_ud.admin.domain.reports import canonical_value
from acciones_ud.shared.infrastructure.http_errors import error_responses
from acciones_ud.shared.infrastructure.request_meta import request_meta

router = APIRouter(
    tags=["admin-halts"],
    route_class=AuditRoute,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)


@router.get("/admin/trading-halts", response_model=s.AdminPageOut[s.HaltOut])
async def page(
    request: Request,
    user: HaltsAdmin,
    scope: str | None = None,
    status: str | None = None,
    cursor: str | None = None,
    page_size: Size = 20,
) -> object:
    return canonical_value(
        await request.app.state.admin_halts.page(scope, status, cursor, page_size)
    )


@router.post("/admin/trading-halts", response_model=s.HaltOut, status_code=201)
async def activate(body: s.HaltIn, request: Request, user: HaltsAdmin) -> object:
    return canonical_value(
        await request.app.state.admin_halts.activate(
            body.scope,
            body.reason,
            body.starts_at,
            body.ends_at,
            user.user_id,
            body.totp_code,
            request_meta(request),
        )
    )


@router.post("/admin/trading-halts/{halt_id}/release", response_model=s.HaltOut)
async def release(
    halt_id: UUID, body: s.AdminDecisionIn, request: Request, user: HaltsAdmin
) -> object:
    return canonical_value(
        await request.app.state.admin_halts.release(
            halt_id, body.reason, user.user_id, body.totp_code, request_meta(request)
        )
    )


@router.get("/trading-halts/active", response_model=list[s.PublicHaltOut])
async def active(request: Request, user: Authenticated) -> object:
    return canonical_value(await request.app.state.admin_halts.active_public())
