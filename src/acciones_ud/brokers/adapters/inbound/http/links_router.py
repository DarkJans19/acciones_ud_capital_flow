from uuid import UUID

from fastapi import APIRouter, Request

from acciones_ud.brokers.adapters.inbound.http.deps import (
    HistoryPeriod,
    Investor,
    PageSize,
    context,
)
from acciones_ud.brokers.adapters.inbound.http.schemas import requests as q
from acciones_ud.brokers.adapters.inbound.http.schemas import responses as s
from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.brokers.domain.entities import LinkStatus
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/broker-links", tags=["broker-links"], responses=error_responses(422))


@router.post(
    "",
    status_code=201,
    response_model=s.LinkResponse,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def request_link(body: q.LinkIn, request: Request, user: Investor) -> object:
    service = LinkService(context(request))
    return await service.view(
        await service.request_link(user.user_id, body.broker_id, body.consent_accepted)
    )


@router.get(
    "/current", response_model=s.CurrentLinkResponse, responses=error_responses(401, 403, 503)
)
async def current(request: Request, user: Investor) -> object:
    return await LinkService(context(request)).current(user.user_id)


@router.get("", response_model=s.LinkPage, responses=error_responses(401, 403, 422, 503))
async def history(
    request: Request,
    user: Investor,
    period: HistoryPeriod,
    status: LinkStatus | None = None,
    cursor: str | None = None,
    page_size: PageSize = 20,
) -> object:
    return await LinkService(context(request)).history(
        user.user_id, status, period, cursor, page_size
    )


@router.post(
    "/{id}/cancel",
    response_model=s.LinkResponse,
    responses=error_responses(401, 403, 404, 409, 503),
)
async def cancel(id: UUID, request: Request, user: Investor) -> object:
    service = LinkService(context(request))
    return await service.view(await service.cancel(user.user_id, id))


@router.post(
    "/{id}/end",
    response_model=s.LinkResponse,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def end(id: UUID, body: q.EndLinkIn, request: Request, user: Investor) -> object:
    service = LinkService(context(request))
    return await service.view(await service.end_link(user.user_id, id, body.reason, body.confirmed))


@router.put(
    "/{id}/order-review",
    response_model=s.LinkResponse,
    responses=error_responses(401, 403, 404, 409, 503),
)
async def order_review(id: UUID, body: q.OrderReviewIn, request: Request, user: Investor) -> object:
    service = LinkService(context(request))
    return await service.view(await service.set_order_review(user.user_id, id, body.enabled))


@router.post(
    "/{id}/trading-authorization",
    status_code=201,
    response_model=s.TradingAuthorizationResponse,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def authorize(id: UUID, body: q.ConsentIn, request: Request, user: Investor) -> object:
    return await LinkService(context(request)).grant_trading(
        user.user_id, id, body.consent_accepted
    )


@router.post(
    "/{id}/trading-authorization/revoke",
    response_model=s.TradingAuthorizationResponse,
    responses=error_responses(401, 403, 404, 409, 503),
)
async def revoke(id: UUID, request: Request, user: Investor) -> object:
    return await LinkService(context(request)).revoke_trading(user.user_id, id)
