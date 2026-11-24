import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from acciones_ud.shared.domain.errors import AppError, ErrorCode

ORDER_HTTP_STATUSES = {
    ErrorCode.TRADING_HALTED: 503,
    ErrorCode.ACCOUNT_TRADING_RESTRICTED: 403,
    ErrorCode.INVALID_PERIOD: 422,
    ErrorCode.ACCOUNT_NOT_LINKED: 409,
    ErrorCode.ORDER_ACCOUNT_NOT_ACTIVE: 409,
    ErrorCode.QUOTE_UNAVAILABLE: 503,
    ErrorCode.ASSET_NOT_TRADABLE: 422,
    ErrorCode.INSUFFICIENT_BUYING_POWER: 409,
    ErrorCode.INSUFFICIENT_POSITION: 409,
    ErrorCode.DAILY_ORDER_LIMIT_REACHED: 409,
    ErrorCode.EXTRA_AUTHORIZATION_REQUIRED: 409,
    ErrorCode.EXTRA_AUTHORIZATION_INVALID: 401,
    ErrorCode.ORDER_REJECTED: 422,
    ErrorCode.ORDER_NOT_FOUND: 404,
    ErrorCode.INVALID_ORDER_STATE: 409,
    ErrorCode.ORDER_NOT_CANCELLABLE: 409,
    ErrorCode.MARKET_CLOSED: 409,
    ErrorCode.MFA_ENROLLMENT_REQUIRED: 409,
}

ADMIN_HTTP_STATUSES = {
    ErrorCode.FEE_VERSION_CONFLICT: 409,
    ErrorCode.FEE_VERSION_NOT_CANCELABLE: 409,
    ErrorCode.TRADING_HALT_OVERLAP: 409,
    ErrorCode.TRADING_HALT_NOT_RELEASABLE: 409,
    ErrorCode.RESTRICTION_ALREADY_ACTIVE: 409,
    ErrorCode.RESTRICTION_NOT_ACTIVE: 409,
    ErrorCode.PROTECTED_PERMISSION: 409,
}


BROKERS_HTTP_STATUSES = {
    ErrorCode.BROKER_NOT_FOUND: 404,
    ErrorCode.CONSENT_REQUIRED: 422,
    ErrorCode.LINK_ALREADY_EXISTS: 409,
    ErrorCode.INVALID_LINK_STATE: 409,
    ErrorCode.LINK_NOT_FOUND: 404,
    ErrorCode.PROPOSAL_NOT_FOUND: 404,
    ErrorCode.PROPOSAL_VERSION_CONFLICT: 409,
    ErrorCode.INVALID_PROPOSAL_STATE: 409,
    ErrorCode.TRADING_AUTHORIZATION_REQUIRED: 409,
    ErrorCode.RATING_NOT_ALLOWED: 409,
    ErrorCode.CLIENT_NOT_FOUND: 404,
    ErrorCode.CONFIRMATION_REQUIRED: 422,
}


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] | None = None


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    # Endpoints that use persistence can also encounter a deployment/schema
    # error, distinct from a retryable connection failure (503).
    declared = {*statuses, 409, 500} if 503 in statuses else set(statuses)
    return {status: {"model": ErrorBody} for status in sorted(declared)}


def error_body_response(exc: AppError) -> JSONResponse:
    """Shared Error_Body response used by the handler and by logout on 503 (4.14)."""
    return JSONResponse(
        status_code=BROKERS_HTTP_STATUSES.get(
            exc.code,
            ADMIN_HTTP_STATUSES.get(exc.code, ORDER_HTTP_STATUSES.get(exc.code, exc.status)),
        ),
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        response = error_body_response(exc)
        if exc.code == ErrorCode.REFRESH_INVALID:
            from acciones_ud.shared.infrastructure.cookies import clear_auth_cookies

            clear_auth_cookies(response, request.app.state.settings)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Validator messages can include supplied values. Return safe issue types only.
        errors = [
            {"field": ".".join(str(x) for x in e["loc"]), "issue": e["type"]} for e in exc.errors()
        ]
        first = errors[0]["field"] if errors else "request"
        details: dict[str, object] = {"errors": errors}
        if request.url.path.startswith(
            ("/api/v1/wallet", "/api/v1/subscriptions", "/api/v1/orders")
        ):
            details = {"fields": [entry["field"] for entry in errors]}
        return JSONResponse(
            status_code=422,
            content={
                "code": ErrorCode.VALIDATION_ERROR,
                "message": f"Invalid field: {first}",
                "details": details,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = {404: ErrorCode.NOT_FOUND, 405: ErrorCode.METHOD_NOT_ALLOWED}.get(
            exc.status_code, ErrorCode.HTTP_ERROR
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code,
                "message": "HTTP request failed.",
                "details": None,
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Exception text and traceback can contain credentials or request values.
        logging.getLogger(__name__).error(
            "Unexpected request failure",
            extra={"request_id": getattr(request.state, "request_id", "")},
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "An unexpected error occurred.",
                "details": None,
            },
            headers={"X-Request-ID": getattr(request.state, "request_id", "")},
        )
