# Feature: identity-market-backend, Property 23: Stream fan-out

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.entities import PriceUpdate
from acciones_ud.market_data.domain.streaming import SubscriptionRegistry

CATALOG = {"AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "V", "KO"}
CLIENTS = st.sampled_from(["c1", "c2", "c3"])
SUBSCRIPTIONS = st.lists(st.sampled_from(sorted(CATALOG)), max_size=35)
UPDATES = st.lists(
    st.sampled_from(sorted(CATALOG)), max_size=20
).map(lambda symbols: [PriceUpdate(symbol=symbol, price=Decimal("1")) for symbol in symbols])


@given(
    messages=st.lists(st.tuples(CLIENTS, SUBSCRIPTIONS), max_size=12),
    updates=UPDATES,
)
def test_stream_fan_out(
    messages: list[tuple[str, list[str]]],
    updates: list[PriceUpdate],
) -> None:
    registry = SubscriptionRegistry()
    accepted: dict[str, set[str]] = {}

    for client, symbols in messages:
        before = accepted.get(client, set())
        if registry.subscribe(client, symbols, CATALOG):
            accepted[client] = {symbol.upper() for symbol in symbols}
        else:
            assert registry.symbols(client) == before

    expected: list[tuple[str, str]] = []
    for update in updates:
        for client, symbols in accepted.items():
            if update.symbol in symbols:
                expected.append((client, update.symbol))

    delivered: list[tuple[str, str]] = []
    for update in updates:
        for client, _ in sorted(registry.fan_out(update).items()):
            delivered.append((client, update.symbol))

    assert sorted(delivered) == sorted(expected)
    assert registry.upstream() == {
        symbol for symbols in accepted.values() for symbol in symbols
    }
