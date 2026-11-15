import httpx
import pytest

from acciones_ud.orders.adapters.outbound.alpaca.orders_client import AlpacaOrdersClient
from acciones_ud.orders.domain.errors import (
    AlpacaRejectedError,
    OrderSubmissionNotReceived,
    OrderSubmissionUnknown,
)


@pytest.mark.parametrize(
    "outcome,expected",
    [
        (429, OrderSubmissionNotReceived),
        (422, AlpacaRejectedError),
        (503, OrderSubmissionUnknown),
        (httpx.ReadTimeout("timeout"), OrderSubmissionUnknown),
        (httpx.ConnectError("connection"), OrderSubmissionNotReceived),
    ],
)
async def test_submission_classification(outcome, expected) -> None:
    def handle(request):
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(outcome, json={"message": "Provider rejected parameters"})

    async with httpx.AsyncClient(
        base_url="https://alpaca.test", transport=httpx.MockTransport(handle)
    ) as http:
        with pytest.raises(expected) as caught:
            await AlpacaOrdersClient(http).create("account", {"client_order_id": "local"}, 4)
        if outcome == 503:
            assert caught.value.server_error
