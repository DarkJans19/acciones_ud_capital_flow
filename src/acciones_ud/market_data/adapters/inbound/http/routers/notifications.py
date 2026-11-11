from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.market_data.adapters.inbound.http.schemas.watchlists import NotificationOut
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/notifications", tags=["Notifications"])

User = Annotated[CurrentUser, Depends(get_current_user)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get(
    "", response_model=list[NotificationOut], responses=error_responses(401, 422)
)
async def list_notifications(
    request: Request,
    user: User,
    page_size: PageSize = 20,
) -> list[NotificationOut]:
    from acciones_ud.market_data.composition import notifier

    items = await notifier(request).list_in_app(user.user_id, page_size)
    return [NotificationOut.of(item) for item in items]
