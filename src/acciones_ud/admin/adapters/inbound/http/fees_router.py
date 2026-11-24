from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from acciones_ud.admin.adapters.inbound.http import schemas as s
from acciones_ud.admin.adapters.inbound.http.deps import AuditRoute, FeesAdmin
from acciones_ud.admin.domain.reports import canonical_value
from acciones_ud.shared.infrastructure.http_errors import error_responses
from acciones_ud.shared.infrastructure.request_meta import request_meta

router = APIRouter(
    prefix="/admin/fee-schedules",
    tags=["admin-fees"],
    route_class=AuditRoute,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)


@router.get("", response_model=s.MatrixOut)
async def matrix(request: Request, user: FeesAdmin) -> object:
    return canonical_value(await request.app.state.admin_fees.matrix())


@router.get("/{scope}/versions", response_model=s.AdminPageOut[s.FeeOut])
async def history(
    scope: str,
    request: Request,
    user: FeesAdmin,
    cursor: str | None = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> object:
    return canonical_value(await request.app.state.admin_fees.history(scope, cursor, page_size))


@router.post("/{scope}/versions", response_model=s.FeeOut, status_code=201)
async def create(scope: str, body: s.FeeIn, request: Request, user: FeesAdmin) -> object:
    return canonical_value(
        await request.app.state.admin_fees.create(
            scope,
            body.commission_rate_pct,
            body.platform_share_pct,
            body.effective_from,
            body.reason,
            body.expected_latest_version,
            user.user_id,
            body.totp_code,
            request_meta(request),
        )
    )


@router.post("/{scope}/versions/{version_id}/cancel", response_model=s.FeeOut)
async def cancel(
    scope: str, version_id: UUID, body: s.AdminDecisionIn, request: Request, user: FeesAdmin
) -> object:
    return canonical_value(
        await request.app.state.admin_fees.cancel(
            scope, version_id, body.reason, user.user_id, body.totp_code, request_meta(request)
        )
    )
