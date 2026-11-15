from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from acciones_ud.shared.domain.alpaca_errors import (
    AlpacaUnavailable,
    AlpacaValidationError,
    classify,
)
from acciones_ud.shared.infrastructure.alpaca_http import raise_for_alpaca
from acciones_ud.wallet.domain.model import (
    Activity,
    ActivityPage,
    ActivityQuery,
    BankRelationshipInput,
    Direction,
    Raw,
)


def provider_time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result


class AlpacaFundingClient:
    def __init__(self, client: httpx.AsyncClient | Callable[[], httpx.AsyncClient]) -> None:
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client() if callable(self._client) else self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: Raw | None = None,
        params: Raw | None = None,
        timeout: float = 10,
    ) -> object:
        try:
            response = await self.client.request(
                method, path, json=body, params=params, timeout=timeout
            )
            if response.status_code in {400, 409, 422} and path.endswith("/transfers"):
                try:
                    reason = str(response.json().get("message", "Alpaca rejected the transfer."))
                except ValueError:
                    reason = "Alpaca rejected the transfer."
                raise AlpacaValidationError(reason[:300])
            raise_for_alpaca(response)
            return response.json()
        except httpx.HTTPError as exc:
            raise classify(exc) from None
        except (ValueError, TypeError):
            raise AlpacaUnavailable() from None

    async def get_trading_account(self, account_id: str, timeout_s: float = 5) -> Raw:
        result = await self._request(
            "GET", f"/v1/trading/accounts/{account_id}/account", timeout=timeout_s
        )
        if not isinstance(result, dict):
            raise AlpacaUnavailable()
        return result

    async def create_ach_relationship(self, account_id: str, data: BankRelationshipInput) -> Raw:
        result = await self._request(
            "POST", f"/v1/accounts/{account_id}/ach_relationships", body=asdict(data)
        )
        if not isinstance(result, dict):
            raise AlpacaUnavailable()
        return result

    async def list_ach_relationships(self, account_id: str) -> list[Raw]:
        result = await self._request("GET", f"/v1/accounts/{account_id}/ach_relationships")
        if not isinstance(result, list):
            raise AlpacaUnavailable()
        return result

    async def create_transfer(
        self, account_id: str, relationship_id: str, amount: Decimal, direction: Direction
    ) -> Raw:
        result = await self._request(
            "POST",
            f"/v1/accounts/{account_id}/transfers",
            body={
                "transfer_type": "ach",
                "relationship_id": relationship_id,
                "amount": str(amount),
                "direction": direction,
            },
        )
        if not isinstance(result, dict):
            raise AlpacaUnavailable()
        return result

    async def list_transfers(self, account_id: str) -> list[Raw]:
        collected: list[Raw] = []
        while True:
            page = await self._request(
                "GET",
                f"/v1/accounts/{account_id}/transfers",
                params={"limit": 100, "offset": len(collected)},
            )
            if not isinstance(page, list):
                raise AlpacaUnavailable()
            collected.extend(page)
            if len(page) < 100:
                return collected

    async def list_activities(self, query: ActivityQuery) -> ActivityPage:
        params: Raw = {
            "account_id": query.account_id,
            "after": query.after.isoformat(),
            "until": query.until.isoformat(),
            "page_size": query.page_size,
            "direction": "asc",
        }
        if query.types:
            params["activity_types"] = ",".join(query.types)
        if query.page_token:
            params["page_token"] = query.page_token
        result = await self._request("GET", "/v1/accounts/activities", params=params)
        if not isinstance(result, list):
            raise AlpacaUnavailable()
        items = [
            Activity(
                id=str(v["id"]),
                type=str(v["activity_type"]),
                date=provider_time(v.get("transaction_time") or v["date"]),
                amount=v.get("net_amount"),
                currency=v.get("currency") or "USD",
                direction=v.get("direction"),
                status=v.get("status"),
                description=v.get("description"),
                side=v.get("side"),
                symbol=v.get("symbol"),
                qty=v.get("qty"),
                price=v.get("price"),
            )
            for v in result
        ]
        return ActivityPage(items, items[-1].id if len(items) == query.page_size else None)
