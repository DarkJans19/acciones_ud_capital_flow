import asyncio
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response

from acciones_ud.orders.adapters.inbound.http.deps import Investor, orders
from acciones_ud.orders.adapters.inbound.http.schemas import orders as s
from acciones_ud.orders.domain.model import OrderStatus
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/orders", tags=["orders"], responses=error_responses(422))
Key = Annotated[str, Header(alias="Idempotency-Key", pattern=r"^[\x20-\x7e]{8,128}$")]
CREATION_DEADLINE_SECONDS = 5.0


@router.post(
    "/preview", response_model=s.PreviewOut, responses=error_responses(401, 403, 409, 422, 502, 503)
)
async def preview(body: s.OrderIn, request: Request, user: Investor) -> object:
    return await orders(request).preview(user.user_id, body.to_request())


@router.post(
    "",
    response_model=s.OrderOut,
    status_code=201,
    responses=error_responses(401, 403, 409, 422, 502, 503),
)
async def create(body: s.OrderIn, request: Request, user: Investor, key: Key) -> object:
    try:
        async with asyncio.timeout(CREATION_DEADLINE_SECONDS):
            order = await orders(request).create(
                user.user_id, body.to_request(), key, body.totp_code
            )
            return await orders(request).get(user.user_id, order.id)
    except TimeoutError:
        # TX1 precedes every POST. A timed-out caller retries the same key; a staged
        # order remains SUBMITTED and is resolved by reconciliation, never resubmitted.
        raise AppError(
            502,
            ErrorCode.ALPACA_UNAVAILABLE,
            "Order response deadline exceeded; retry with the same Idempotency-Key.",
        ) from None


@router.get("", response_model=s.OrderPageOut, responses=error_responses(401, 403, 422, 503))
async def list_orders(
    request: Request,
    user: Investor,
    status: OrderStatus | None = None,
    symbol: str | None = None,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> object:
    return await orders(request).list(user.user_id, status, symbol, start, end, page_size, cursor)


@router.get("/{id}", response_model=s.OrderOut, responses=error_responses(401, 403, 404, 422, 503))
async def get_order(id: UUID, request: Request, user: Investor) -> object:
    return await orders(request).get(user.user_id, id)


@router.post(
    "/{id}/cancel",
    response_model=s.OrderOut,
    responses={
        **error_responses(401, 403, 404, 409, 422, 502, 503),
        202: {"model": s.OrderOut, "description": "Cancellation pending Alpaca confirmation."},
    },
)
async def cancel(
    id: UUID, body: s.CancelIn, request: Request, response: Response, user: Investor
) -> object:
    order, status = await orders(request).cancel(
        user.user_id, id, body.reason, body.reason_text, body.confirmed
    )
    response.status_code = status
    return await orders(request).get(user.user_id, order.id)


@router.post(
    "/{id}/reauthorization",
    response_model=s.OrderOut,
    responses=error_responses(401, 403, 404, 409, 422, 502, 503),
)
async def reauthorize(
    id: UUID, body: s.ReauthorizationIn, request: Request, user: Investor
) -> object:
    order = await orders(request).answer_reauthorization(user.user_id, id, body.decision)
    return await orders(request).get(user.user_id, order.id)


@router.post(
    "/{id}/resubmit",
    response_model=s.OrderOut,
    responses=error_responses(401, 403, 404, 409, 422, 502, 503),
)
async def resubmit(id: UUID, body: s.ResubmitIn, request: Request, user: Investor) -> object:
    order = await orders(request).resubmit(user.user_id, id, body.changes(), body.totp_code)
    return await orders(request).get(user.user_id, order.id)


@router.post(
    "/{id}/resume",
    response_model=s.OrderOut,
    responses=error_responses(401, 403, 404, 409, 422, 502, 503),
)
async def resume(id: UUID, request: Request, user: Investor) -> object:
    order = await orders(request).resume(user.user_id, id)
    return await orders(request).get(user.user_id, order.id)
