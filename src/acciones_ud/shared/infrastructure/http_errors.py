import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from acciones_ud.shared.domain.errors import AppError, ErrorCode


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] | None = None


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return {status: {"model": ErrorBody} for status in statuses}


def error_body_response(exc: AppError) -> JSONResponse:
    """Shared Error_Body response used by the handler and by logout on 503 (4.14)."""
    return JSONResponse(
        status_code=exc.status,
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
        return JSONResponse(
            status_code=422,
            content={
                "code": ErrorCode.VALIDATION_ERROR,
                "message": f"Invalid field: {first}",
                "details": {"errors": errors},
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
