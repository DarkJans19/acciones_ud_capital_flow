from typing import Annotated

from fastapi import APIRouter, Depends, Request

from acciones_ud.identity.adapters.inbound.http.deps import require_permission
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.market_data.adapters.inbound.http.schemas.dashboard import DashboardOut
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(tags=["Dashboard"])

MarketReader = Annotated[CurrentUser, Depends(require_permission("market:read"))]


@router.get(
    "/dashboard", response_model=DashboardOut, responses=error_responses(401, 403)
)
async def dashboard(request: Request, user: MarketReader) -> DashboardOut:
    from acciones_ud.market_data.composition import dashboard_service

    return DashboardOut.of(await dashboard_service(request).dashboard(user.user_id))
