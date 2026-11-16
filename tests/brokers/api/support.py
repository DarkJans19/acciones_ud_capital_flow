from uuid import UUID, uuid4

from fastapi import FastAPI, Request

from acciones_ud.brokers.adapters.inbound.http import (
    broker_clients_router,
    broker_links_router,
    broker_proposals_router,
    directory_router,
    links_router,
    proposals_router,
)
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.infrastructure.http_errors import register_exception_handlers


def app_for(ctx):
    app = FastAPI()
    app.state.brokers_context = ctx
    register_exception_handlers(app)
    for module in (
        directory_router,
        links_router,
        proposals_router,
        broker_links_router,
        broker_proposals_router,
        broker_clients_router,
    ):
        app.include_router(module.router, prefix="/api/v1")

    async def user(request: Request):
        ctx = request.app.state.brokers_context
        try:
            actor = UUID(request.cookies.get("access_token", ""))
            if actor not in ctx.directory.names:
                raise ValueError()
        except ValueError:
            raise AppError(401, ErrorCode.NOT_AUTHENTICATED, "Authentication required.") from None
        return CurrentUser(
            actor,
            uuid4(),
            "test@example.test",
            "active",
            False,
            frozenset(ctx.directory.roles.get(actor, set())),
        )

    app.dependency_overrides[get_current_user] = user
    return app
