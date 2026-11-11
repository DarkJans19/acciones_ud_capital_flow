from types import SimpleNamespace
from typing import Any, cast

from acciones_ud.market_data.adapters.outbound.alpaca.data_client import AlpacaDataClient
from acciones_ud.market_data.composition import data_client


def app_state(api_settings: Any) -> SimpleNamespace:
    return SimpleNamespace(settings=api_settings, alpaca_data=object())


def test_raw_http_client_is_not_used_as_the_data_port(api_settings: Any) -> None:
    request = cast(Any, SimpleNamespace(app=SimpleNamespace(state=app_state(api_settings))))
    port = data_client(request)
    assert isinstance(port, AlpacaDataClient)


def test_explicit_override_wins(api_settings: Any) -> None:
    fake = object()
    state = app_state(api_settings)
    state.alpaca_data_port = fake
    request = cast(Any, SimpleNamespace(app=SimpleNamespace(state=state)))
    assert data_client(request) is fake
