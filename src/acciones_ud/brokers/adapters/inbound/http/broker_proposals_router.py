from uuid import UUID

from fastapi import APIRouter, Request

from acciones_ud.brokers.adapters.inbound.http.deps import Broker, HistoryPeriod, PageSize, context
from acciones_ud.brokers.adapters.inbound.http.schemas import requests as q
from acciones_ud.brokers.adapters.inbound.http.schemas import responses as s
from acciones_ud.brokers.application.message_service import MessageService
from acciones_ud.brokers.application.proposal_service import ProposalService
from acciones_ud.brokers.domain.entities import ProposalStatus
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(
    prefix="/broker/proposals", tags=["broker-portal"], responses=error_responses(422)
)


@router.post(
    "",
    status_code=201,
    response_model=s.ProposalDetail,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def create(body: q.ProposalIn, request: Request, user: Broker) -> object:
    service = ProposalService(context(request))
    proposal = await service.create(user.user_id, body.investor_id, body.content())
    return await service.detail(user.user_id, "broker", proposal.id)


@router.get("", response_model=s.ProposalPage, responses=error_responses(401, 403, 422, 503))
async def history(
    request: Request,
    user: Broker,
    period: HistoryPeriod,
    status: ProposalStatus | None = None,
    cursor: str | None = None,
    page_size: PageSize = 20,
) -> object:
    return await ProposalService(context(request)).history_broker(
        user.user_id, status, period, cursor, page_size
    )


@router.get("/{id}", response_model=s.ProposalDetail, responses=error_responses(401, 403, 404, 503))
async def detail(id: UUID, request: Request, user: Broker) -> object:
    return await ProposalService(context(request)).detail(user.user_id, "broker", id)


@router.put(
    "/{id}",
    response_model=s.ProposalDetail,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def modify(id: UUID, body: q.ModifyProposalIn, request: Request, user: Broker) -> object:
    service = ProposalService(context(request))
    await service.modify(user.user_id, id, body.version, body.content())
    return await service.detail(user.user_id, "broker", id)


@router.post(
    "/{id}/withdraw",
    response_model=s.ProposalDetail,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def withdraw(id: UUID, body: q.WithdrawProposalIn, request: Request, user: Broker) -> object:
    service = ProposalService(context(request))
    await service.withdraw(user.user_id, id, body.version, body.reason, body.confirmed)
    return await service.detail(user.user_id, "broker", id)


@router.post(
    "/{id}/decision",
    response_model=s.ProposalDetail,
    responses=error_responses(401, 403, 404, 409, 422, 502, 503),
)
async def decide(id: UUID, body: q.BrokerDecisionIn, request: Request, user: Broker) -> object:
    service = ProposalService(context(request))
    await service.broker_decide(
        user.user_id, id, body.version, body.decision, body.evidence_message_ids, body.evidence_text
    )
    return await service.detail(user.user_id, "broker", id)


@router.post(
    "/{id}/messages",
    status_code=201,
    response_model=s.Message,
    responses=error_responses(401, 403, 404, 422, 503),
)
async def post_message(id: UUID, body: q.MessageIn, request: Request, user: Broker) -> object:
    return await MessageService(context(request)).post(user.user_id, "broker", id, body.body)


@router.get(
    "/{id}/messages",
    response_model=s.MessagePage,
    responses=error_responses(401, 403, 404, 422, 503),
)
async def thread(
    id: UUID, request: Request, user: Broker, cursor: str | None = None, page_size: PageSize = 20
) -> object:
    return await MessageService(context(request)).thread(
        user.user_id, "broker", id, cursor, page_size
    )
