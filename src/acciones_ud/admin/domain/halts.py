from collections.abc import Iterable
from datetime import datetime

from acciones_ud.admin.domain.model import AccountRestriction, TradingHalt
from acciones_ud.shared.domain.trading import GateDecision


def effective_status(halt: TradingHalt, at: datetime) -> str:
    if halt.released_at is not None and halt.released_at <= at:
        return "released"
    if at < halt.starts_at:
        return "scheduled"
    if halt.ends_at is not None and at >= halt.ends_at:
        return "expired"
    return "active"


def overlaps(a: datetime, a_end: datetime | None, b: datetime, b_end: datetime | None) -> bool:
    return (b_end is None or a < b_end) and (a_end is None or b < a_end)


def gate(
    halts: Iterable[TradingHalt],
    restriction: AccountRestriction | None,
    market: str,
    at: datetime,
) -> GateDecision:
    active = sorted(
        (h for h in halts if h.scope in {"global", market} and effective_status(h, at) == "active"),
        key=lambda h: (h.scope != "global", h.starts_at, h.id),
    )
    if active:
        halt = active[0]
        return GateDecision(
            False,
            "TRADING_HALTED",
            {
                "halt_id": str(halt.id),
                "scope": halt.scope,
                "ends_at": halt.ends_at.isoformat() if halt.ends_at else None,
            },
        )
    if restriction and restriction.lifted_at is None:
        return GateDecision(False, "ACCOUNT_TRADING_RESTRICTED")
    return GateDecision()
