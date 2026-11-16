from datetime import date
from typing import Annotated, cast

from fastapi import Depends, Query, Request

from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.domain.entities import Period
from acciones_ud.brokers.domain.errors import ValidationError
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user, require_broker
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.errors import AppError, ErrorCode


async def require_investor(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.account_status != "active" or "investor" not in user.roles:
        raise AppError(403, ErrorCode.FORBIDDEN, "Investor role required.")
    return user


Investor = Annotated[CurrentUser, Depends(require_investor)]
Broker = Annotated[CurrentUser, Depends(require_broker)]
Authenticated = Annotated[CurrentUser, Depends(get_current_user)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def context(request: Request) -> BrokerContext:
    return cast(BrokerContext, request.app.state.brokers_context)


def period_query(
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> Period | None:
    if start is None and end is None:
        return None
    if start is None or end is None:
        raise ValidationError("from", "both_dates_required")
    return Period(start, end)


HistoryPeriod = Annotated[Period | None, Depends(period_query)]
