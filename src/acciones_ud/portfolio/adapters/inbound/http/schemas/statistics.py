from acciones_ud.portfolio.adapters.inbound.http.schemas.common import DecimalStr, Output


class ShareResponse(Output):
    key: str
    volume: DecimalStr
    percentage: DecimalStr


class StatisticsResponse(Output):
    execution_count: int
    buy_count: int
    sell_count: int
    volume: DecimalStr
    by_market: list[ShareResponse]
    by_instrument: list[ShareResponse]
    by_sector: list[ShareResponse]
