from uuid import UUID

from fastapi import APIRouter, Request

from acciones_ud.orders.adapters.inbound.http.deps import Broker, orders, reviews
from acciones_ud.orders.adapters.inbound.http.schemas import orders as s
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(
    prefix="/broker/order-reviews", tags=["broker-reviews"], responses=error_responses(422)
)


@router.get("", response_model=list[s.OrderSummary], responses=error_responses(401, 403, 503))
async def queue(request: Request, user: Broker) -> object:
    return await reviews(request).queue(user.user_id)


@router.post(
    "/{id}/return",
    response_model=s.OrderOut,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def return_order(id: UUID, body: s.ReturnIn, request: Request, user: Broker) -> object:
    order = await reviews(request).return_for_changes(user.user_id, id, body.comment)
    return await orders(request).get(order.user_id, order.id)


@router.post(
    "/{id}/approve",
    response_model=s.OrderOut,
    responses=error_responses(401, 403, 404, 409, 422, 502, 503),
)
async def approve(id: UUID, request: Request, user: Broker) -> object:
    order = await reviews(request).approve(user.user_id, id)
    return await orders(request).get(order.user_id, order.id)
