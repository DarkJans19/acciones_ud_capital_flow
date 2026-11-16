from decimal import Decimal, localcontext

from acciones_ud.portfolio.domain.model import CommissionQuote, ExecutionRecord


class ReferenceCommission:
    def __init__(self, rate: Decimal = Decimal("0.02")) -> None:
        self.rate = rate

    def commission(self, execution: ExecutionRecord) -> CommissionQuote:
        with localcontext() as ctx:
            ctx.prec = 40
            return CommissionQuote(execution.qty * execution.price * self.rate, "reference")
