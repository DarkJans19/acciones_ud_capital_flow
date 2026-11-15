"""Programmable offline adapter; production composition always selects the HTTP clients."""

from collections import Counter
from decimal import Decimal
from uuid import uuid4

from acciones_ud.orders.domain.errors import OrderSubmissionUnknown
from acciones_ud.orders.domain.model import Raw
from acciones_ud.orders.domain.ports import CancelOutcome


class FakeOrders:
    def __init__(self) -> None:
        self.orders: dict[tuple[str, str], Raw] = {}
        self.creations: Counter[str] = Counter()
        self.outcomes: list[Exception | Raw] = []
        self.store_on_unknown = False
        self.lookup_found = True
        self.fills: dict[str, list[Raw]] = {}
        self.positions: dict[tuple[str, str], Decimal] = {}
        self.cancel_outcome: CancelOutcome = "accepted"
        self.cancel_calls = 0
        self.failure: Exception | None = None

    async def create(self, account_id: str, submission: Raw, timeout_s: float) -> Raw:
        client_id = submission["client_order_id"]
        self.creations[client_id] += 1
        raw = {**submission, "id": str(uuid4()), "status": "new", "filled_qty": "0", "legs": []}
        outcome = self.outcomes.pop(0) if self.outcomes else raw
        if isinstance(outcome, Exception):
            if isinstance(outcome, OrderSubmissionUnknown) and self.store_on_unknown:
                self.orders[(account_id, client_id)] = raw
            raise outcome
        self.orders[(account_id, client_id)] = outcome
        return outcome

    async def get_by_client_order_id(self, account_id: str, client_order_id: str) -> Raw | None:
        if self.failure:
            raise self.failure
        return self.orders.get((account_id, client_order_id)) if self.lookup_found else None

    async def get(self, account_id: str, alpaca_order_id: str) -> Raw:
        if self.failure:
            raise self.failure
        return next(
            v
            for (account, _), v in self.orders.items()
            if account == account_id and v["id"] == alpaca_order_id
        )

    async def cancel(self, account_id: str, alpaca_order_id: str) -> CancelOutcome:
        if self.failure:
            raise self.failure
        self.cancel_calls += 1
        if self.cancel_outcome == "accepted":
            raw = await self.get(account_id, alpaca_order_id)
            raw["status"] = "canceled"
        return self.cancel_outcome

    async def list_fills(self, account_id: str, after_id: str | None) -> list[Raw]:
        if self.failure:
            raise self.failure
        values = self.fills.get(account_id, [])
        start = next((i + 1 for i, v in enumerate(values) if v["id"] == after_id), 0)
        return list(values[start:])

    async def qty_available(self, alpaca_account_id: str, symbol: str) -> Decimal:
        if self.failure:
            raise self.failure
        return self.positions.get((alpaca_account_id, symbol), Decimal(0))
