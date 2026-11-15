from fastapi import FastAPI

from acciones_ud.orders.adapters.inbound.http.routers.broker_reviews import router as broker_router
from acciones_ud.orders.adapters.inbound.http.routers.orders import router
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.shared.infrastructure.http_errors import register_exception_handlers


def api_for(context):
    app = FastAPI()
    register_exception_handlers(app)
    service = OrderService(context)
    app.state.order_service = service
    app.state.order_review_service = service.reviews
    app.include_router(router, prefix="/api/v1")
    app.include_router(broker_router, prefix="/api/v1")
    return app
