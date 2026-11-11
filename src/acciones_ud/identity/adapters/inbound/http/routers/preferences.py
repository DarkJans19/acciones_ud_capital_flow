from typing import Annotated

from fastapi import APIRouter, Depends, Request

from acciones_ud.identity.adapters.inbound.http.deps import require_permission
from acciones_ud.identity.adapters.inbound.http.schemas.preferences import (
    OrderControlsIn,
    PortfolioViewIn,
    PreferencesIn,
    TelegramIn,
)
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(tags=["preferences"])
User = Annotated[CurrentUser, Depends(require_permission("account:manage"))]


@router.get(
    "/users/preferences/channels",
    response_model=PreferencesIn,
    responses=error_responses(401, 403, 503),
)
async def channels(request: Request, user: User) -> Record:
    from acciones_ud.identity.composition import account_service

    return await account_service(request).preferences(user.user_id)


@router.put(
    "/users/preferences/channels",
    response_model=PreferencesIn,
    responses=error_responses(401, 403, 422, 503),
)
async def put_channels(body: PreferencesIn, request: Request, user: User) -> Record:
    from acciones_ud.identity.composition import account_service

    return await account_service(request).preferences(
        user.user_id, [p.model_dump() for p in body.preferences]
    )


@router.get(
    "/users/preferences/portfolio",
    response_model=PortfolioViewIn,
    responses=error_responses(401, 403, 503),
)
async def portfolio(request: Request, user: User) -> Record:
    from acciones_ud.identity.composition import account_service

    return await account_service(request).settings(user.user_id, "portfolio")


@router.put(
    "/users/preferences/portfolio",
    response_model=PortfolioViewIn,
    responses=error_responses(401, 403, 422, 503),
)
async def put_portfolio(body: PortfolioViewIn, request: Request, user: User) -> Record:
    from acciones_ud.identity.composition import account_service

    return await account_service(request).settings(user.user_id, "portfolio", body.model_dump())


@router.get(
    "/users/preferences/orders",
    response_model=OrderControlsIn,
    responses=error_responses(401, 403, 503),
)
async def orders(request: Request, user: User) -> Record:
    from acciones_ud.identity.composition import account_service

    return await account_service(request).settings(user.user_id, "orders")


@router.put(
    "/users/preferences/orders",
    response_model=OrderControlsIn,
    responses=error_responses(401, 403, 422, 503),
)
async def put_orders(body: OrderControlsIn, request: Request, user: User) -> Record:
    from acciones_ud.identity.composition import account_service

    return await account_service(request).settings(user.user_id, "orders", body.model_dump())


@router.put(
    "/users/me/telegram", response_model=TelegramIn, responses=error_responses(401, 403, 422, 503)
)
async def telegram(body: TelegramIn, request: Request, user: User) -> Record:
    from acciones_ud.identity.composition import account_service

    return await account_service(request).telegram(user.user_id, body.chat_id)
