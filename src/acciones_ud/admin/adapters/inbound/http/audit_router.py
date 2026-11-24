from uuid import UUID

from fastapi import APIRouter, Request

from acciones_ud.admin.adapters.inbound.http import schemas as s
from acciones_ud.admin.adapters.inbound.http.commissions_router import From, Size, To
from acciones_ud.admin.adapters.inbound.http.deps import AuditReader, AuditRoute
from acciones_ud.admin.domain.errors import not_found
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.reports import canonical_value
from acciones_ud.shared.infrastructure.http_errors import error_responses

GUARANTEE = (
    "Append-only evidence enforced by application and PostgreSQL triggers. "
    "Schema owners and superusers can disable triggers; this is not absolute "
    "immutability or a certification of regulatory compliance."
)
router = APIRouter(
    prefix="/admin/audit-trail",
    tags=["admin-audit"],
    route_class=AuditRoute,
    responses=error_responses(401, 403, 404, 422, 503),
)


@router.get("", response_model=s.AdminPageOut[s.TrailEventOut], description=GUARANTEE)
async def page(
    request: Request,
    user: AuditReader,
    from_: From,
    to: To,
    user_id: UUID | None = None,
    source: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    cursor: str | None = None,
    page_size: Size = 50,
) -> object:
    return canonical_value(
        await request.app.state.admin_trail.page(
            *Period(from_, to).bounds(),
            {
                "user_id": user_id,
                "source": source,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
            },
            cursor,
            page_size,
        )
    )


@router.get("/orders/{order_id}", response_model=s.OrderCustodyOut, description=GUARANTEE)
async def custody(order_id: UUID, request: Request, user: AuditReader) -> object:
    result = await request.app.state.admin_trail.order_custody(order_id)
    if result is None:
        raise not_found("order")
    return canonical_value(result)
