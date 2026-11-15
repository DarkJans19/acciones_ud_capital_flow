from uuid import uuid4

import httpx
import pytest

from acciones_ud.wallet.adapters.outbound.stripe.stripe_client import StripeClient
from acciones_ud.wallet.domain.errors import StripeRejectedError, StripeUnavailableError


@pytest.mark.parametrize(
    "status,error",
    [(429, StripeUnavailableError), (503, StripeUnavailableError), (400, StripeRejectedError)],
)
async def test_stripe_classification(status, error) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["Stripe-Version"] == "2024-06-20"
        assert b"mode=subscription" in request.content
        return httpx.Response(status)

    async with httpx.AsyncClient(
        base_url="https://stripe.test", transport=httpx.MockTransport(handle)
    ) as http:
        with pytest.raises(error):
            await StripeClient(
                http, "sk_test_fake", "http://success.test", "http://cancel.test"
            ).create_checkout_session(uuid4(), "price_test")
