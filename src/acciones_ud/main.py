from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from acciones_ud.config.settings import Settings, get_settings, require_api_settings
from acciones_ud.identity import composition as identity
from acciones_ud.market_data import composition as market_data
from acciones_ud.shared.infrastructure.alpaca_http import build_client
from acciones_ud.shared.infrastructure.alpaca_oauth import build_oauth_client
from acciones_ud.shared.infrastructure.http_errors import register_exception_handlers
from acciones_ud.shared.infrastructure.logging import RequestIdMiddleware, configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        require_api_settings(settings)
        configure_logging(settings)

        def alpaca_client(base_url: str) -> httpx.AsyncClient:
            if settings.client_id and settings.client_secret and settings.alpaca_auth_url:
                return build_oauth_client(
                    base_url,
                    settings.alpaca_auth_url,
                    settings.client_id.get_secret_value(),
                    settings.client_secret.get_secret_value(),
                )
            assert settings.alpaca_broker_api_key and settings.alpaca_broker_api_secret
            return build_client(
                base_url,
                settings.alpaca_broker_api_key.get_secret_value(),
                settings.alpaca_broker_api_secret.get_secret_value(),
            )

        async with AsyncExitStack() as stack:
            app.state.alpaca_broker = await stack.enter_async_context(
                alpaca_client(settings.alpaca_broker_base_url or "")
            )
            app.state.alpaca_data = await stack.enter_async_context(
                alpaca_client(settings.alpaca_data_base_url or "")
            )
            await identity.startup(app)
            stack.push_async_callback(identity.shutdown, app)
            await market_data.startup(app)
            stack.push_async_callback(market_data.shutdown, app)
            yield

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    identity.register(app)
    market_data.register(app)

    default_openapi = app.openapi

    def openapi_with_optional_logout() -> dict[str, Any]:
        # Logout accepts either cookie or neither (4.6, 4.11, 4.12); FastAPI has no
        # first-class way to add the "no credentials" alternative to `security`.
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = default_openapi()
        operation = schema.get("paths", {}).get("/api/v1/auth/logout", {}).get("post")
        if operation is not None:
            operation["security"] = [
                {"AccessTokenCookie": []},
                {"RefreshTokenCookie": []},
                {},
            ]
        app.openapi_schema = schema
        return schema

    app.openapi = openapi_with_optional_logout  # type: ignore[method-assign]

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
