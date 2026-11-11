from typing import Annotated

from fastapi import APIRouter, Depends, Request

from acciones_ud.identity.adapters.inbound.http.deps import require_permission
from acciones_ud.identity.adapters.inbound.http.schemas.kyc import (
    KycAccountOut,
    KycStatusOut,
    KycSubmissionIn,
)
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.clock import SystemClock
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/kyc", tags=["KYC"])


@router.get("/status", response_model=KycStatusOut, responses=error_responses(401, 403, 503))
async def status(
    request: Request, user: Annotated[CurrentUser, Depends(require_permission("kyc:submit"))]
) -> Record:
    from acciones_ud.identity.composition import kyc_service

    return await kyc_service(request).status(user.user_id)


@router.post(
    "/account",
    status_code=201,
    response_model=KycAccountOut,
    responses=error_responses(401, 403, 409, 422, 500, 502, 503),
)
async def submit(
    body: KycSubmissionIn,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("kyc:submit"))],
) -> Record:
    from acciones_ud.identity.composition import kyc_service

    opening = body.to_request(SystemClock().now(), request.client.host if request.client else "")
    return await kyc_service(request).submit(user.user_id, opening)
