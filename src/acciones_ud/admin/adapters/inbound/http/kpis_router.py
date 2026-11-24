from fastapi import APIRouter, Request

from acciones_ud.admin.adapters.inbound.http import schemas as s
from acciones_ud.admin.adapters.inbound.http.commissions_router import From, To
from acciones_ud.admin.adapters.inbound.http.deps import AuditRoute, BiReader
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.reports import canonical_value
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(
    tags=["admin-bi"], route_class=AuditRoute, responses=error_responses(401, 403, 422, 503)
)


@router.get("/admin/kpis", response_model=s.KpiOut)
async def dashboard(
    request: Request, user: BiReader, from_: From, to: To, refresh: bool = False
) -> object:
    return canonical_value(await request.app.state.admin_kpis.dashboard(Period(from_, to), refresh))
