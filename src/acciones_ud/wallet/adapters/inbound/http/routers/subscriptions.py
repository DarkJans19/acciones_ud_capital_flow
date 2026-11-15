from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.infrastructure.http_errors import error_responses
from acciones_ud.wallet.adapters.inbound.http import schemas as s
from acciones_ud.wallet.adapters.inbound.http.deps import require_investor
from acciones_ud.wallet.application.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"], responses=error_responses(422))
User = Annotated[CurrentUser, Depends(require_investor)]


def service(request: Request) -> SubscriptionService:
    return cast(SubscriptionService, request.app.state.subscription_service)


@router.get("/plans", response_model=list[s.PlanOut], responses=error_responses(401, 403))
async def plans(request: Request, user: User) -> object:
    return service(request).list_plans()


@router.post(
    "/checkout",
    response_model=s.CheckoutOut,
    status_code=201,
    responses=error_responses(401, 403, 409, 422, 502, 503),
)
async def checkout(body: s.CheckoutIn, request: Request, user: User) -> object:
    return await service(request).start_checkout(user.user_id, body.plan)


@router.post(
    "/me/cancel",
    response_model=s.SubscriptionOut,
    responses=error_responses(401, 403, 409, 422, 502, 503),
)
async def cancel(body: s.CancelIn, request: Request, user: User) -> object:
    return await service(request).cancel(user.user_id, body.reason)


@router.get(
    "/me", response_model=s.CurrentSubscriptionOut, responses=error_responses(401, 403, 503)
)
async def current(request: Request, user: User) -> object:
    return await service(request).get_current(user.user_id)


@router.get(
    "/me/payments",
    response_model=s.PageOut[s.PaymentOut],
    responses=error_responses(401, 403, 422, 503),
)
async def payments(
    request: Request,
    user: User,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> object:
    return await service(request).list_payments(user.user_id, page_size, cursor)


@router.get(
    "/me/payments/{id}", response_model=s.PaymentOut, responses=error_responses(401, 403, 404, 503)
)
async def payment(id: UUID, request: Request, user: User) -> object:
    return await service(request).get_payment(user.user_id, id)
