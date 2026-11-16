from uuid import UUID

from fastapi import APIRouter, Request

from acciones_ud.brokers.adapters.inbound.http.deps import Broker, context
from acciones_ud.brokers.adapters.inbound.http.schemas import requests as q
from acciones_ud.brokers.adapters.inbound.http.schemas import responses as s
from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(
    prefix="/broker/link-requests", tags=["broker-portal"], responses=error_responses(422)
)


@router.get("", response_model=list[s.LinkRequest], responses=error_responses(401, 403, 503))
async def pending(request: Request, user: Broker) -> object:
    return await LinkService(context(request)).pending_requests(user.user_id)


@router.post(
    "/{id}/accept",
    response_model=s.LinkResponse,
    responses=error_responses(401, 403, 404, 409, 503),
)
async def accept(id: UUID, request: Request, user: Broker) -> object:
    service = LinkService(context(request))
    return await service.view(await service.accept(user.user_id, id))


@router.post(
    "/{id}/decline",
    response_model=s.LinkResponse,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def decline(id: UUID, body: q.ReasonIn, request: Request, user: Broker) -> object:
    service = LinkService(context(request))
    return await service.view(await service.decline(user.user_id, id, body.reason))
