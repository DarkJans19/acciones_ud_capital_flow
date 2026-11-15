from collections.abc import Callable
from uuid import UUID

import httpx

from acciones_ud.wallet.domain.errors import StripeRejectedError, StripeUnavailableError
from acciones_ud.wallet.domain.model import Raw


class StripeClient:
    def __init__(
        self,
        client: httpx.AsyncClient | Callable[[], httpx.AsyncClient],
        secret: str,
        success_url: str,
        cancel_url: str,
    ) -> None:
        self._client, self.secret = client, secret
        self.success_url, self.cancel_url = success_url, cancel_url

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client() if callable(self._client) else self._client

    async def _request(self, method: str, path: str, data: dict[str, str]) -> Raw:
        try:
            response = await self.client.request(
                method,
                path,
                data=data,
                timeout=10,
                headers={"Authorization": f"Bearer {self.secret}", "Stripe-Version": "2024-06-20"},
            )
        except httpx.HTTPError:
            raise StripeUnavailableError() from None
        if response.status_code == 429 or response.status_code >= 500:
            raise StripeUnavailableError()
        if not response.is_success:
            raise StripeRejectedError()
        try:
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except ValueError:
            raise StripeUnavailableError() from None

    async def create_checkout_session(self, user_id: UUID, price_id: str) -> Raw:
        return await self._request(
            "POST",
            "/v1/checkout/sessions",
            {
                "mode": "subscription",
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                "client_reference_id": str(user_id),
                "metadata[user_id]": str(user_id),
                "subscription_data[metadata][user_id]": str(user_id),
                "success_url": self.success_url,
                "cancel_url": self.cancel_url,
            },
        )

    async def cancel_at_period_end(self, stripe_subscription_id: str) -> Raw:
        return await self._request(
            "POST", f"/v1/subscriptions/{stripe_subscription_id}", {"cancel_at_period_end": "true"}
        )

    async def get_subscription(self, stripe_subscription_id: str) -> Raw:
        return await self._request("GET", f"/v1/subscriptions/{stripe_subscription_id}", {})
