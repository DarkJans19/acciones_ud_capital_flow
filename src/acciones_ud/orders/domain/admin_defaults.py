from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from acciones_ud.shared.domain.trading import CommissionTerms, GateDecision


@dataclass(frozen=True)
class ReferenceCommissionTerms:
    rate: Decimal = Decimal("0.02")

    async def terms(self, exchange: str, at: datetime) -> CommissionTerms:
        return CommissionTerms(None, self.rate * 100, Decimal("60.00"))


class AllowAllGate:
    async def check(self, user_id: UUID, exchange: str, at: datetime) -> GateDecision:
        return GateDecision()
