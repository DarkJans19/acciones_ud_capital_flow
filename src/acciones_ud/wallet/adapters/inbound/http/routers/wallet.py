from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.infrastructure.http_errors import error_responses
from acciones_ud.wallet.adapters.inbound.http import schemas as s
from acciones_ud.wallet.adapters.inbound.http.deps import require_investor
from acciones_ud.wallet.application.funding_service import FundingService
from acciones_ud.wallet.application.wallet_service import WalletService
from acciones_ud.wallet.domain.model import BankRelationshipInput

router = APIRouter(prefix="/wallet", tags=["wallet"], responses=error_responses(422))
User = Annotated[CurrentUser, Depends(require_investor)]
Key = Annotated[str, Header(alias="Idempotency-Key", pattern=r"^[\x20-\x7e]{8,128}$")]


def funding(request: Request) -> FundingService:
    return cast(FundingService, request.app.state.funding_service)


def wallet(request: Request) -> WalletService:
    return cast(WalletService, request.app.state.wallet_service)


@router.get("/balances", response_model=s.BalanceOut, responses=error_responses(401, 403, 409, 503))
async def balances(request: Request, user: User) -> object:
    return await wallet(request).get_balances(user.user_id)


@router.get(
    "/currencies",
    response_model=s.CurrenciesOut,
    responses=error_responses(401, 403, 409, 502, 503),
)
async def currencies(request: Request, user: User) -> object:
    return await wallet(request).get_currencies(user.user_id)


@router.post(
    "/bank-relationships",
    response_model=s.BankOut,
    status_code=201,
    responses=error_responses(401, 403, 409, 422, 502, 503),
)
async def bank_create(body: s.BankIn, request: Request, user: User) -> object:
    return await funding(request).create_bank_relationship(
        user.user_id, BankRelationshipInput(**body.model_dump())
    )


@router.get(
    "/bank-relationships",
    response_model=list[s.BankOut],
    responses=error_responses(401, 403, 409, 502, 503),
)
async def bank_list(request: Request, user: User) -> object:
    return await funding(request).list_bank_relationships(user.user_id)


@router.get(
    "/bank-relationships/{id}",
    response_model=s.BankOut,
    responses=error_responses(401, 403, 404, 503),
)
async def bank_get(id: UUID, request: Request, user: User) -> object:
    return await funding(request).get_bank_relationship(user.user_id, id)


@router.post(
    "/deposits",
    response_model=s.TransferOut,
    status_code=201,
    responses=error_responses(401, 403, 409, 422, 502, 503),
)
async def deposit(body: s.TransferIn, request: Request, user: User, key: Key) -> object:
    return await funding(request).request_transfer(
        user.user_id, "INCOMING", body.bank_relationship_id, body.amount, body.currency, key
    )


@router.post(
    "/withdrawals",
    response_model=s.TransferOut,
    status_code=201,
    responses=error_responses(401, 403, 409, 422, 502, 503),
)
async def withdrawal(body: s.TransferIn, request: Request, user: User, key: Key) -> object:
    return await funding(request).request_transfer(
        user.user_id, "OUTGOING", body.bank_relationship_id, body.amount, body.currency, key
    )


@router.get(
    "/transfers",
    response_model=s.PageOut[s.TransferOut],
    responses=error_responses(401, 403, 409, 422, 503),
)
async def transfers(
    request: Request,
    user: User,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    direction: str | None = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> object:
    return await funding(request).list_transfers(
        user.user_id, start, end, direction, page_size, cursor
    )


@router.get(
    "/transfers/{id}", response_model=s.TransferOut, responses=error_responses(401, 403, 404, 503)
)
async def transfer_get(id: UUID, request: Request, user: User) -> object:
    return await funding(request).get_transfer(user.user_id, id)


@router.get(
    "/activities",
    response_model=s.PageOut[s.ActivityOut],
    responses=error_responses(401, 403, 409, 422, 502, 503),
)
async def activities(
    request: Request,
    user: User,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    types: str | None = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> object:
    return await wallet(request).list_activities(
        user.user_id, start, end, tuple(types.split(",")) if types else (), page_size, cursor
    )
