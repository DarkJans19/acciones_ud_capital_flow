from decimal import Decimal

from acciones_ud.admin.domain.commissions import compute, terms_from
from acciones_ud.portfolio.adapters.outbound.commissions.reference_commission import (
    ReferenceCommission,
)
from acciones_ud.portfolio.domain.model import CommissionQuote, ExecutionRecord


class OfficialCommission:
    def __init__(self, reference_rate: Decimal = Decimal("0.02")) -> None:
        self.reference = ReferenceCommission(reference_rate)

    def commission(self, execution: ExecutionRecord) -> CommissionQuote:
        terms = terms_from(
            execution.commission_rate_pct, execution.platform_share_pct, execution.fee_version_id
        )
        if terms is None:
            return self.reference.commission(execution)
        result = compute(
            terms,
            execution.side,
            execution.qty,
            execution.price,
            execution.signed_by_broker_id is not None,
        )
        return CommissionQuote(result.commission, "official")
