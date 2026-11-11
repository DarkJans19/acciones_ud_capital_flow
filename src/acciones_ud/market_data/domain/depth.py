"""RF-25 / Property 39: top-of-book depth from the latest quote document."""

from acciones_ud.market_data.domain.entities import DepthLevel, DepthResult, LatestQuoteDoc


def from_latest_quote(document: LatestQuoteDoc) -> DepthResult:
    if document.quote is None:
        return DepthResult(levels=(), as_of=None, full_depth_available=False)
    quote = document.quote
    return DepthResult(
        levels=(
            DepthLevel(
                bid_price=quote.bid_price,
                bid_size=quote.bid_size,
                ask_price=quote.ask_price,
                ask_size=quote.ask_size,
            ),
        ),
        as_of=quote.timestamp,
        full_depth_available=False,
    )
