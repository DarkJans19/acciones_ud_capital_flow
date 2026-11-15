from typing import cast

from fastapi import APIRouter, Request

from acciones_ud.shared.domain.clock import SystemClock
from acciones_ud.shared.infrastructure.http_errors import error_responses
from acciones_ud.wallet.adapters.inbound.http.schemas import ReceivedOut
from acciones_ud.wallet.application.stripe_webhook_service import StripeWebhookService

router = APIRouter(tags=["subscriptions"])


@router.post(
    "/webhooks/stripe", response_model=ReceivedOut, responses=error_responses(400, 502, 503)
)
async def stripe_webhook(request: Request) -> object:
    body = await request.body()
    service = cast(StripeWebhookService, request.app.state.stripe_webhook_service)
    clock = getattr(request.app.state, "wallet_clock", None) or SystemClock()
    return await service.handle(body, request.headers.get("Stripe-Signature"), clock.now())
