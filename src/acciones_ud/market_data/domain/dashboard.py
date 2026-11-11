"""RFP-08 / Property 16: dashboard assembly (pure)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from acciones_ud.market_data.domain.entities import Instrument, Snapshot

MAX_INSTRUMENTS = 10


@dataclass(frozen=True)
class DashboardInstrument:
    symbol: str
    name: str
    price: Decimal | None
    quote_timestamp: datetime | None
    quote_unavailable: bool


@dataclass(frozen=True)
class DashboardData:
    level: str | None
    beginner: bool
    source: str
    instruments: list[DashboardInstrument]


def _matches(instrument: Instrument, interests: list[str]) -> bool:
    wanted = {interest.strip().lower() for interest in interests}
    return instrument.exchange.lower() in wanted or (
        instrument.sector is not None and instrument.sector.lower() in wanted
    )


def select_instruments(
    instruments: list[Instrument],
    interests: list[str],
    default_symbols: list[str],
) -> tuple[list[Instrument], str]:
    by_symbol = {instrument.symbol: instrument for instrument in instruments}
    matching = [
        instrument
        for instrument in instruments
        if instrument.listed and _matches(instrument, interests)
    ]
    if matching:
        selected = sorted(matching, key=lambda item: item.symbol)[:MAX_INSTRUMENTS]
        return selected, "interests"
    fallback = [
        by_symbol[symbol]
        for symbol in default_symbols
        if symbol in by_symbol and by_symbol[symbol].listed
    ]
    selected = sorted(fallback, key=lambda item: item.symbol)[:MAX_INSTRUMENTS]
    return selected, "default"


def assemble(
    instruments: list[Instrument],
    interests: list[str],
    default_symbols: list[str],
    quotes: dict[str, Snapshot],
    level: str | None,
) -> DashboardData:
    selected, source = select_instruments(instruments, interests, default_symbols)
    rows: list[DashboardInstrument] = []
    for instrument in selected:
        quote = quotes.get(instrument.symbol)
        if quote is None or quote.last_trade_price is None:
            rows.append(
                DashboardInstrument(
                    symbol=instrument.symbol,
                    name=instrument.name,
                    price=None,
                    quote_timestamp=None,
                    quote_unavailable=True,
                )
            )
            continue
        rows.append(
            DashboardInstrument(
                symbol=instrument.symbol,
                name=instrument.name,
                price=quote.last_trade_price,
                quote_timestamp=quote.quote_updated_at,
                quote_unavailable=False,
            )
        )
    return DashboardData(
        level=level if level in {"beginner", "experienced"} else None,
        beginner=level == "beginner",
        source=source,
        instruments=rows,
    )
