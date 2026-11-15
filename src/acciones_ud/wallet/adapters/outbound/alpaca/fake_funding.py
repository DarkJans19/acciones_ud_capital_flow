"""Deterministic offline Broker API adapter for tests; never selected in production."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from acciones_ud.wallet.domain.model import (
    Activity,
    ActivityPage,
    ActivityQuery,
    BankRelationshipInput,
    Direction,
    Raw,
)


class FakeFunding:
    def __init__(self) -> None:
        self.accounts: dict[str, Raw] = {}
        self.relationships: dict[str, list[Raw]] = {}
        self.transfers: dict[str, list[Raw]] = {}
        self.activities: dict[str, list[Activity]] = {}
        self.creations = 0
        self.failure: Exception | None = None

    def _check(self) -> None:
        if self.failure:
            raise self.failure

    async def get_trading_account(self, account_id: str, timeout_s: float = 5) -> Raw:
        self._check()
        return self.accounts[account_id]

    async def create_ach_relationship(self, account_id: str, data: BankRelationshipInput) -> Raw:
        self._check()
        result = {
            "id": str(uuid4()),
            "status": "APPROVED",
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.relationships.setdefault(account_id, []).append(result)
        return result

    async def list_ach_relationships(self, account_id: str) -> list[Raw]:
        self._check()
        return self.relationships.get(account_id, [])

    async def create_transfer(
        self, account_id: str, relationship_id: str, amount: Decimal, direction: Direction
    ) -> Raw:
        self._check()
        self.creations += 1
        at = datetime.now(UTC).isoformat()
        result = {
            "id": str(uuid4()),
            "status": "QUEUED",
            "amount": str(amount),
            "currency": "USD",
            "direction": direction,
            "created_at": at,
            "updated_at": at,
        }
        self.transfers.setdefault(account_id, []).append(result)
        return result

    async def list_transfers(self, account_id: str) -> list[Raw]:
        self._check()
        return self.transfers.get(account_id, [])

    async def list_activities(self, query: ActivityQuery) -> ActivityPage:
        self._check()
        values = sorted(
            [
                v
                for v in self.activities.get(query.account_id, [])
                if query.after <= v.date <= query.until
                and (not query.types or v.type in query.types)
            ],
            key=lambda v: (v.date, v.id),
        )
        if query.page_token:
            values = values[
                next(
                    (i + 1 for i, v in enumerate(values) if v.id == query.page_token), len(values)
                ) :
            ]
        page = values[: query.page_size]
        return ActivityPage(page, page[-1].id if len(page) == query.page_size else None)
