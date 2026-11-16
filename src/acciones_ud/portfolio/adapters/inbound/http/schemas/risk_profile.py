from datetime import datetime
from typing import Literal

from acciones_ud.portfolio.adapters.inbound.http.schemas.common import DecimalStr, Output


class RiskMetrics(Output):
    execution_count: int
    executions_per_week: DecimalStr
    volume: DecimalStr
    markets: list[str]
    instruments: list[str]
    asset_distribution: dict[str, DecimalStr]
    window_from: datetime
    window_to: datetime


class RiskProfileResponse(Output):
    window_days: int
    f: DecimalStr
    c: DecimalStr
    e: DecimalStr
    t: DecimalStr
    risk_score: DecimalStr | None
    classification: Literal["conservative", "moderate", "aggressive", "insufficient_data"]
    equity_unavailable: bool
    metrics: RiskMetrics
