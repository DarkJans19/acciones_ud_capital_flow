from decimal import Decimal

import httpx

from acciones_ud.wallet.adapters.outbound.alpaca.funding_client import AlpacaFundingClient


async def test_transfer_sends_exact_amount_and_ach_route() -> None:
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "external", "status": "QUEUED"})

    async with httpx.AsyncClient(
        base_url="https://alpaca.test", transport=httpx.MockTransport(handle)
    ) as http:
        client = AlpacaFundingClient(http)
        await client.create_transfer("account", "relationship", Decimal("12.34"), "INCOMING")
    assert requests[0].url.path == "/v1/accounts/account/transfers"
    assert b'"amount":"12.34"' in requests[0].content
    assert b'"transfer_type":"ach"' in requests[0].content
