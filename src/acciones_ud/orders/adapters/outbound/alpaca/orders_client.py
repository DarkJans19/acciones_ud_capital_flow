from collections.abc import Callable

import httpx

from acciones_ud.orders.domain.errors import (
    AlpacaRejectedError,
    OrderSubmissionNotReceived,
    OrderSubmissionUnknown,
)
from acciones_ud.orders.domain.model import Raw
from acciones_ud.orders.domain.ports import CancelOutcome
from acciones_ud.shared.domain.alpaca_errors import AlpacaUnavailable, classify
from acciones_ud.shared.infrastructure.alpaca_http import raise_for_alpaca


class AlpacaOrdersClient:
    def __init__(self, client: httpx.AsyncClient | Callable[[], httpx.AsyncClient]) -> None:
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client() if callable(self._client) else self._client

    async def create(self, account_id: str, submission: Raw, timeout_s: float) -> Raw:
        try:
            response = await self.client.post(
                f"/v1/trading/accounts/{account_id}/orders", json=submission, timeout=timeout_s
            )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            raise OrderSubmissionNotReceived() from None
        except httpx.HTTPError:
            raise OrderSubmissionUnknown() from None
        if response.status_code == 429:
            raise OrderSubmissionNotReceived(rate_limited=True)
        if response.status_code >= 500:
            raise OrderSubmissionUnknown(server_error=True)
        if response.status_code in {400, 409, 422}:
            try:
                message = str(response.json().get("message") or "Alpaca rejected the order.")
            except ValueError:
                message = "Alpaca rejected the order."
            raise AlpacaRejectedError(message)
        if not response.is_success:
            raise OrderSubmissionNotReceived()
        try:
            result = response.json()
            if not isinstance(result, dict) or not result.get("id"):
                raise ValueError()
            return result
        except ValueError:
            raise OrderSubmissionUnknown() from None

    async def _get(self, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        try:
            return await self.client.get(path, params=params, timeout=4)
        except httpx.HTTPError as exc:
            raise classify(exc) from None

    @staticmethod
    def _document(response: httpx.Response) -> Raw:
        raise_for_alpaca(response)
        try:
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except ValueError:
            raise AlpacaUnavailable() from None

    async def get_by_client_order_id(self, account_id: str, client_order_id: str) -> Raw | None:
        response = await self._get(
            f"/v1/trading/accounts/{account_id}/orders:by_client_order_id",
            {"client_order_id": client_order_id},
        )
        return None if response.status_code == 404 else self._document(response)

    async def get(self, account_id: str, alpaca_order_id: str) -> Raw:
        return self._document(
            await self._get(
                f"/v1/trading/accounts/{account_id}/orders/{alpaca_order_id}", {"nested": "true"}
            )
        )

    async def cancel(self, account_id: str, alpaca_order_id: str) -> CancelOutcome:
        try:
            response = await self.client.delete(
                f"/v1/trading/accounts/{account_id}/orders/{alpaca_order_id}", timeout=4
            )
        except httpx.HTTPError as exc:
            raise classify(exc) from None
        if response.status_code == 422:
            return "not_cancelable"
        raise_for_alpaca(response)
        return "accepted"

    async def list_fills(self, account_id: str, after_id: str | None) -> list[Raw]:
        collected: list[Raw] = []
        token = after_id
        while True:
            params = {
                "account_id": account_id,
                "activity_types": "FILL",
                "direction": "asc",
                "page_size": "100",
            }
            if token:
                params["page_token"] = token
            response = await self._get("/v1/accounts/activities", params)
            raise_for_alpaca(response)
            try:
                page = response.json()
                if not isinstance(page, list):
                    raise ValueError()
            except ValueError:
                raise AlpacaUnavailable() from None
            collected.extend(page)
            if len(page) < 100:
                return collected
            next_token = str(page[-1]["id"])
            if next_token == token:
                raise AlpacaUnavailable()
            token = next_token
