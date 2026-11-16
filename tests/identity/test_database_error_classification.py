import logging

import pytest
from sqlalchemy.exc import DBAPIError

from acciones_ud.shared.infrastructure.db import database_error, translate_database_errors


class DriverFailure(Exception):
    def __init__(self, state: str) -> None:
        super().__init__("secret password and personal data")
        self.sqlstate = state


@pytest.mark.parametrize(
    ("state", "status", "code"),
    [
        ("42P01", 500, "DATABASE_SCHEMA_ERROR"),
        ("42703", 500, "DATABASE_SCHEMA_ERROR"),
        ("42501", 500, "DATABASE_PERMISSION_ERROR"),
        ("28P01", 500, "DATABASE_PERMISSION_ERROR"),
        ("23503", 409, "DATABASE_INTEGRITY_ERROR"),
        ("23505", 409, "DATABASE_INTEGRITY_ERROR"),
        ("23514", 409, "DATABASE_INTEGRITY_ERROR"),
        ("22P02", 500, "DATABASE_DATA_ERROR"),
        ("08006", 503, "DATABASE_UNAVAILABLE"),
        ("malicious secret", 503, "DATABASE_UNAVAILABLE"),
    ],
)
async def test_sql_failures_are_classified_without_leaking_data(
    state: str, status: int, code: str, caplog: pytest.LogCaptureFixture
) -> None:
    from acciones_ud.shared.domain.errors import AppError

    error = DBAPIError("SELECT sensitive", {"password": "secret"}, DriverFailure(state))
    with caplog.at_level(logging.ERROR), pytest.raises(AppError) as caught:
        async with translate_database_errors():
            raise error
    assert caught.value.status == status
    assert caught.value.code == code
    assert caught.value.details is None
    assert "secret" not in caplog.text
    assert "sensitive" not in caplog.text
    if len(state) == 5:
        assert state in caplog.text


def test_connection_failure_remains_retryable() -> None:
    error = database_error(ConnectionRefusedError("secret connection string"))
    assert error.status == 503
    assert error.code == "DATABASE_UNAVAILABLE"


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (500, "DATABASE_SCHEMA_ERROR"),
        (500, "DATABASE_PERMISSION_ERROR"),
        (409, "DATABASE_INTEGRITY_ERROR"),
        (500, "DATABASE_DATA_ERROR"),
    ],
)
async def test_logout_clears_cookies_for_all_database_failures(
    status: int, code: str, api_settings: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import httpx

    from acciones_ud.identity import composition
    from acciones_ud.main import create_app
    from acciones_ud.shared.domain.errors import AppError, ErrorCode

    service = SimpleNamespace(
        logout=AsyncMock(side_effect=AppError(status, ErrorCode(code), "Failed"))
    )
    monkeypatch.setattr(composition, "session_service", lambda request: service)
    app = create_app(api_settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.test"
    ) as client:
        result = await client.post("/api/v1/auth/logout")
    assert result.status_code == status
    assert result.json()["code"] == code
    assert len(result.headers.get_list("set-cookie")) == 2
    assert all("Max-Age=0" in value for value in result.headers.get_list("set-cookie"))
