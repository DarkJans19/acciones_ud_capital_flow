"""Immutable cross-module contracts; RF-43/45/46, MOD-07 H3."""

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class CommissionTerms:
    fee_version_id: UUID | None
    commission_rate_pct: Decimal
    platform_share_pct: Decimal

    @property
    def broker_share_pct(self) -> Decimal:
        return Decimal(100) - self.platform_share_pct


@dataclass(frozen=True)
class GateDecision:
    allowed: bool = True
    code: str | None = None
    details: dict[str, object] = field(default_factory=dict)
