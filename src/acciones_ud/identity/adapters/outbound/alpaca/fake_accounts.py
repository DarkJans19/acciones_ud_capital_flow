from collections import deque

from acciones_ud.identity.domain.kyc import AlpacaAccount, AlpacaAccountSummary
from acciones_ud.identity.domain.kyc_submission import AccountOpeningRequest


class FakeAlpacaAccounts:
    def __init__(
        self,
        outcomes: list[AlpacaAccount | Exception],
        list_outcomes: list[list[AlpacaAccountSummary] | Exception] | None = None,
    ) -> None:
        self.outcomes = deque(outcomes)
        self.list_outcomes = deque(list_outcomes or [])
        self.calls: list[tuple[str, str | None]] = []

    def _next(self) -> AlpacaAccount:
        outcome = self.outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def create_account(self, request: AccountOpeningRequest) -> AlpacaAccount:
        # Call recording deliberately excludes the PII payload.
        self.calls.append(("create", None))
        return self._next()

    async def get_account(self, account_id: str, timeout: float = 10) -> AlpacaAccount:
        self.calls.append(("get", account_id))
        return self._next()

    async def list_accounts(
        self, query: str, timeout: float = 10
    ) -> list[AlpacaAccountSummary]:
        self.calls.append(("list", query))
        if not self.list_outcomes:
            return []
        outcome = self.list_outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
