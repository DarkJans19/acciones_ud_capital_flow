from fastapi import APIRouter, Request, Response

from acciones_ud.identity.adapters.inbound.http.schemas.auth import (
    LoginIn,
    LoginOut,
    MfaVerifyIn,
    MfaVerifyOut,
    RegisterBrokerIn,
    RegisterInvestorIn,
    RegistrationOut,
)
from acciones_ud.shared.infrastructure.cookies import set_auth_cookies
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    status_code=201,
    response_model=RegistrationOut,
    responses=error_responses(409, 422, 503),
)
async def register_investor(body: RegisterInvestorIn, request: Request) -> dict[str, object]:
    from acciones_ud.identity.composition import registration_service

    return await registration_service(request).register_investor(body.model_dump())


@router.post(
    "/register/broker",
    status_code=201,
    response_model=RegistrationOut,
    responses=error_responses(409, 422, 503),
)
async def register_broker(body: RegisterBrokerIn, request: Request) -> dict[str, object]:
    from acciones_ud.identity.composition import registration_service

    return await registration_service(request).register_broker(body.model_dump())


@router.post("/login", response_model=LoginOut, responses=error_responses(401, 422, 503))
async def login(body: LoginIn, request: Request) -> dict[str, object]:
    from acciones_ud.identity.composition import auth_service

    return await auth_service(request).login(
        body.email,
        body.password,
        request.client.host if request.client else "",
        request.headers.get("user-agent", ""),
    )


@router.post("/mfa/verify", response_model=MfaVerifyOut, responses=error_responses(401, 422, 503))
async def verify_mfa(body: MfaVerifyIn, request: Request, response: Response) -> dict[str, object]:
    from acciones_ud.identity.composition import auth_service

    result = await auth_service(request).verify(
        body.mfa_token,
        body.code,
        body.recovery_code,
        request.client.host if request.client else "",
        request.headers.get("user-agent", ""),
    )
    set_auth_cookies(
        response, result.pop("access"), result.pop("refresh"), request.app.state.settings
    )
    return result
