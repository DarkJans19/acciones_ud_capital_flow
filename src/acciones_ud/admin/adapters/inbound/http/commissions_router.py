from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from acciones_ud.admin.adapters.inbound.http import schemas as s
from acciones_ud.admin.adapters.inbound.http.deps import (
    AuditRoute,
    CommissionsAdmin,
    Investor,
    Trader,
)
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.reports import canonical_value
from acciones_ud.identity.adapters.inbound.http.deps import require_broker
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(
    tags=["commissions"], route_class=AuditRoute, responses=error_responses(401, 403, 404, 422, 503)
)
Broker = Annotated[CurrentUser, Depends(require_broker)]
From = Annotated[date, Query(alias="from")]
To = Annotated[date, Query(alias="to")]
Size = Annotated[int, Query(ge=1, le=100)]


@router.get("/commissions/quote", response_model=s.CommissionQuoteOut)
async def quote(
    request: Request,
    user: Trader,
    symbol: str,
    side: str,
    qty: Annotated[Decimal, Query(gt=0, allow_inf_nan=False)],
    price: Annotated[Decimal, Query(gt=0, allow_inf_nan=False)],
    with_broker: bool = False,
) -> object:
    return canonical_value(
        await request.app.state.admin_quote.quote(symbol, side, qty, price, with_broker)
    )


@router.get("/commissions", response_model=s.CommissionPage)
async def investor_commissions(
    request: Request,
    user: Investor,
    from_: From,
    to: To,
    symbol: str | None = None,
    cursor: str | None = None,
    page_size: Size = 20,
) -> object:
    return canonical_value(
        await request.app.state.admin_commissions.query(
            Period(from_, to), cursor, page_size, investor=user.user_id, symbol=symbol
        )
    )


@router.get("/broker/commissions", response_model=s.CommissionPage)
async def broker_commissions(
    request: Request,
    user: Broker,
    from_: From,
    to: To,
    investor_id: UUID | None = None,
    cursor: str | None = None,
    page_size: Size = 20,
) -> object:
    return canonical_value(
        await request.app.state.admin_commissions.query(
            Period(from_, to),
            cursor,
            page_size,
            investor=investor_id,
            broker=user.user_id,
            broker_view=True,
        )
    )


@router.get("/admin/commissions", response_model=s.CommissionPage)
async def admin_commissions(
    request: Request,
    user: CommissionsAdmin,
    from_: From,
    to: To,
    broker_id: UUID | None = None,
    investor_id: UUID | None = None,
    market: str | None = None,
    cursor: str | None = None,
    page_size: Size = 20,
) -> object:
    return canonical_value(
        await request.app.state.admin_commissions.query(
            Period(from_, to),
            cursor,
            page_size,
            investor=investor_id,
            broker=broker_id,
            market=market,
        )
    )
