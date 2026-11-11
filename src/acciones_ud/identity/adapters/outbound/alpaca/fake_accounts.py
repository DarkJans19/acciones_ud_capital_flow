from collections import deque

from acciones_ud.identity.domain.kyc import AlpacaAccount
from acciones_ud.identity.domain.kyc_submission import AccountOpeningRequest


class FakeAlpacaAccounts:
    def __init__(self, outcomes: list[AlpacaAccount | Exception]) -> None:
        self.outcomes = deque(outcomes)
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
