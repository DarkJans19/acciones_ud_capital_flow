from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from acciones_ud.brokers.adapters.inbound.http.deps import (
    Authenticated,
    Broker,
    Investor,
    PageSize,
    context,
)
from acciones_ud.brokers.adapters.inbound.http.schemas import requests as q
from acciones_ud.brokers.adapters.inbound.http.schemas import responses as s
from acciones_ud.brokers.application.directory_service import DirectoryService
from acciones_ud.brokers.application.rating_service import RatingService
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/brokers", tags=["brokers"], responses=error_responses(422))


@router.get(
    "/suggestions", response_model=list[s.BrokerSummary], responses=error_responses(401, 403, 503)
)
async def suggestions(request: Request, user: Investor) -> object:
    return await DirectoryService(context(request)).suggestions(user.user_id)


@router.get("", response_model=s.BrokerPage, responses=error_responses(401, 403, 422, 503))
async def search(
    request: Request,
    user: Investor,
    q: Annotated[
        str | None,
        Query(
            min_length=2,
            max_length=100,
            description=(
                "Filtro opcional del nombre o firma (2 a 100 caracteres). "
                "Sin filtro lista todos los brokers disponibles por paginas. "
                "Devuelve items con id, nombre, firma, perfil y reputación; "
                "next_cursor permite paginar."
            ),
            examples=["Capital"],
        ),
    ] = None,
    cursor: str | None = None,
    page_size: PageSize = 20,
) -> object:
    return await DirectoryService(context(request)).search(user.user_id, q, cursor, page_size)


@router.put(
    "/me/profile",
    response_model=s.BrokerProfileResponse,
    responses=error_responses(401, 403, 422, 503),
)
async def update_profile(body: q.BrokerProfileIn, request: Request, user: Broker) -> object:
    return await DirectoryService(context(request)).update_profile(
        user.user_id, body.specialty, body.years_experience, body.certifications, body.description
    )


@router.get(
    "/{broker_id}", response_model=s.BrokerProfileResponse, responses=error_responses(404, 503)
)
async def public_profile(broker_id: UUID, request: Request) -> object:
    return await DirectoryService(context(request)).get_profile(broker_id)


@router.get(
    "/{broker_id}/reputation",
    response_model=s.ReputationResponse,
    responses=error_responses(401, 404, 503),
)
async def reputation(broker_id: UUID, request: Request, user: Authenticated) -> object:
    return await RatingService(context(request)).reputation(broker_id)


@router.get(
    "/{broker_id}/reviews", response_model=s.ReviewPage, responses=error_responses(401, 404, 503)
)
async def reviews(
    broker_id: UUID,
    request: Request,
    user: Authenticated,
    cursor: str | None = None,
    page_size: PageSize = 20,
) -> object:
    return await RatingService(context(request)).reviews(broker_id, cursor, page_size)


@router.put(
    "/{broker_id}/rating",
    response_model=s.RatingResponse,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def rate(broker_id: UUID, body: q.RatingIn, request: Request, user: Investor) -> object:
    return await RatingService(context(request)).publish(
        user.user_id, broker_id, body.stars, body.comment
    )
