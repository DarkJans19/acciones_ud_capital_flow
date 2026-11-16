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
from acciones_ud.brokers.application.message_service import MessageService
from acciones_ud.brokers.application.proposal_service import ProposalService
from acciones_ud.brokers.domain.entities import ProposalStatus
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/proposals", tags=["proposals"], responses=error_responses(422))


@router.get("", response_model=s.ProposalPage, responses=error_responses(401, 403, 422, 503))
async def history(
    request: Request,
    user: Investor,
    period: HistoryPeriod,
    status: ProposalStatus | None = None,
    cursor: str | None = None,
    page_size: PageSize = 20,
) -> object:
    return await ProposalService(context(request)).history_investor(
        user.user_id, status, period, cursor, page_size
    )


@router.get("/{id}", response_model=s.ProposalDetail, responses=error_responses(401, 403, 404, 503))
async def detail(id: UUID, request: Request, user: Investor) -> object:
    return await ProposalService(context(request)).detail(user.user_id, "investor", id)


@router.post(
    "/{id}/decision",
    response_model=s.ProposalDetail,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def decide(id: UUID, body: q.InvestorDecisionIn, request: Request, user: Investor) -> object:
    service = ProposalService(context(request))
    await service.investor_decide(
        user.user_id,
        id,
        body.version,
        body.decision,
        body.comment,
        body.totp_code.get_secret_value() if body.totp_code else None,
    )
    return await service.detail(user.user_id, "investor", id)


@router.post(
    "/{id}/messages",
    status_code=201,
    response_model=s.Message,
    responses=error_responses(401, 403, 404, 422, 503),
)
async def post_message(id: UUID, body: q.MessageIn, request: Request, user: Investor) -> object:
    return await MessageService(context(request)).post(user.user_id, "investor", id, body.body)


@router.get(
    "/{id}/messages",
    response_model=s.MessagePage,
    responses=error_responses(401, 403, 404, 422, 503),
)
async def thread(
    id: UUID, request: Request, user: Investor, cursor: str | None = None, page_size: PageSize = 20
) -> object:
    return await MessageService(context(request)).thread(
        user.user_id, "investor", id, cursor, page_size
    )
