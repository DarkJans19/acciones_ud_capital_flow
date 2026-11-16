from datetime import datetime
from typing import Literal
from uuid import UUID

from acciones_ud.portfolio.adapters.inbound.http.schemas.common import DecimalStr, Output
from acciones_ud.portfolio.adapters.inbound.http.schemas.pagination import PageResponse


class ExecutionResponse(Output):
    execution_id: str
    order_id: UUID
    symbol: str
    exchange: str
    side: Literal["buy", "sell"]
    qty: DecimalStr
    price: DecimalStr
    executed_at: datetime
    commission: DecimalStr
    commission_source: Literal["reference", "official"]


class ExecutionPage(PageResponse[ExecutionResponse]):
    pass
