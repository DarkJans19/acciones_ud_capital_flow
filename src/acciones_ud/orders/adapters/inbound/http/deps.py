from typing import Annotated, cast

from fastapi import Depends, Request

from acciones_ud.identity.adapters.inbound.http.deps import require_broker
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.application.review_service import ReviewService
from acciones_ud.wallet.adapters.inbound.http.deps import require_investor

Investor = Annotated[CurrentUser, Depends(require_investor)]
Broker = Annotated[CurrentUser, Depends(require_broker)]


def orders(request: Request) -> OrderService:
    return cast(OrderService, request.app.state.order_service)


def reviews(request: Request) -> ReviewService:
    return cast(ReviewService, request.app.state.order_review_service)
