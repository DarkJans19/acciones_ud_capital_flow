"""RF-25 / Property 23: streaming subscription registry and fan-out."""

from acciones_ud.market_data.domain.entities import PriceUpdate

MAX_SUBSCRIPTIONS = 30
MIN_SUBSCRIPTIONS = 1


class SubscriptionRegistry:
    def __init__(self) -> None:
        self.clients: dict[str, set[str]] = {}

    def subscribe(self, client_id: str, symbols: list[str], catalog: set[str]) -> bool:
        unique = {symbol.upper() for symbol in symbols}
        if not MIN_SUBSCRIPTIONS <= len(unique) <= MAX_SUBSCRIPTIONS:
            return False
        if not unique <= catalog:
            return False
        self.clients[client_id] = unique
        return True

    def disconnect(self, client_id: str) -> None:
        self.clients.pop(client_id, None)

    def symbols(self, client_id: str) -> set[str]:
        return set(self.clients.get(client_id, set()))

    def targets(self, symbol: str) -> set[str]:
        return {
            client_id
            for client_id, symbols in self.clients.items()
            if symbol in symbols
        }

    def upstream(self) -> set[str]:
        union: set[str] = set()
        for symbols in self.clients.values():
            union |= symbols
        return union

    def fan_out(self, update: PriceUpdate) -> dict[str, PriceUpdate]:
        return {
            client_id: update for client_id in self.targets(update.symbol)
        }
