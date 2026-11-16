from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from acciones_ud.brokers.adapters.inbound.http.deps import Broker, PageSize, context
from acciones_ud.brokers.adapters.inbound.http.schemas.responses import ClientSummary
from acciones_ud.brokers.application.client_service import ClientService
from acciones_ud.brokers.domain.ports import OrderFilters
from acciones_ud.orders.adapters.inbound.http.schemas.orders import OrderPageOut
from acciones_ud.orders.domain.model import OrderStatus
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/broker/clients", tags=["broker-portal"], responses=error_responses(422))


@router.get("", response_model=list[ClientSummary], responses=error_responses(401, 403, 503))
async def clients(request: Request, user: Broker) -> object:
    return await ClientService(context(request)).clients(user.user_id)


@router.get(
    "/{investor_id}/orders",
    response_model=OrderPageOut,
    responses=error_responses(401, 403, 404, 422, 503),
)
async def orders(
    investor_id: UUID,
    request: Request,
    user: Broker,
    status: OrderStatus | None = None,
    symbol: str | None = None,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    cursor: str | None = None,
    page_size: PageSize = 20,
) -> object:
    return await ClientService(context(request)).client_orders(
        user.user_id, investor_id, OrderFilters(status, symbol, start, end, page_size, cursor)
    )
