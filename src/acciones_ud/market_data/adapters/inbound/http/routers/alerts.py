from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi import status as http_status

from acciones_ud.identity.adapters.inbound.http.deps import (
    require_permission,
    require_premium,
)
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.market_data.adapters.inbound.http.schemas.watchlists import (
    AlertIn,
    AlertOut,
)
from acciones_ud.market_data.domain.entities import AlertStatus
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/price-alerts", tags=["Price alerts"])

Manager = Annotated[CurrentUser, Depends(require_permission("watchlist:manage"))]
Premium = Annotated[CurrentUser, Depends(require_premium)]


@router.get("", response_model=list[AlertOut], responses=error_responses(401, 403))
async def list_alerts(request: Request, user: Manager, premium: Premium) -> list[AlertOut]:
    from acciones_ud.market_data.composition import alert_service

    alerts = await alert_service(request).list_alerts(user.user_id)
    return [AlertOut.of(alert) for alert in alerts]


@router.post(
    "",
    status_code=201,
    response_model=AlertOut,
    responses=error_responses(401, 403, 404, 422),
)
async def create_alert(
    request: Request, user: Manager, premium: Premium, body: AlertIn
) -> AlertOut:
    from acciones_ud.market_data.composition import alert_service

    alert = await alert_service(request).create(
        user.user_id, body.symbol, body.comparator, body.threshold
    )
    return AlertOut.of(alert)


@router.post(
    "/{alert_id}/activate",
    response_model=AlertOut,
    responses=error_responses(401, 403, 404, 422),
)
async def activate_alert(
    request: Request, user: Manager, premium: Premium, alert_id: UUID
) -> AlertOut:
    from acciones_ud.market_data.composition import alert_service

    return AlertOut.of(
        await alert_service(request).set_status(user.user_id, alert_id, AlertStatus.ACTIVE)
    )


@router.post(
    "/{alert_id}/deactivate",
    response_model=AlertOut,
    responses=error_responses(401, 403, 404, 422),
)
async def deactivate_alert(
    request: Request, user: Manager, premium: Premium, alert_id: UUID
) -> AlertOut:
    from acciones_ud.market_data.composition import alert_service

    return AlertOut.of(
        await alert_service(request).set_status(
            user.user_id, alert_id, AlertStatus.INACTIVE
        )
    )


@router.delete(
    "/{alert_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 403, 404, 422),
)
async def delete_alert(
    request: Request, user: Manager, premium: Premium, alert_id: UUID
) -> Response:
    from acciones_ud.market_data.composition import alert_service

    await alert_service(request).delete(user.user_id, alert_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
