from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from uuid import UUID

from acciones_ud.admin.domain.errors import invalid
from acciones_ud.admin.domain.model import CommissionBreakdown
from acciones_ud.shared.domain.trading import CommissionTerms


def terms_from(
    rate: Decimal | None,
    share: Decimal | None,
    version_id: UUID | None,
) -> CommissionTerms | None:
    # H3: no historical commission is invented from today's seed or configuration.
    if rate is None or share is None:
        return None
    return CommissionTerms(version_id, rate, share)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def compute(
    terms: CommissionTerms,
    side: str,
    qty: Decimal,
    price: Decimal,
    broker_signed: bool,
) -> CommissionBreakdown:
    if side not in {"buy", "sell"}:
        raise invalid("side")
    if any(not v.is_finite() or v <= 0 for v in (qty, price)):
        raise invalid("qty_or_price")
    with localcontext() as ctx:
        ctx.prec = 60
        gross = qty * price
        commission = money(gross * terms.commission_rate_pct / 100)
        platform = (
            money(commission * terms.platform_share_pct / 100) if broker_signed else commission
        )
        return CommissionBreakdown(
            gross,
            commission,
            platform,
            commission - platform,
            money(gross + commission) if side == "buy" else None,
            money(gross - commission) if side == "sell" else None,
        )
