"""RF-24: pure search ranking shared by the reference model and the SQL ordering."""

from acciones_ud.market_data.domain.entities import Classification, Instrument
from acciones_ud.shared.domain.errors import AppError, ErrorCode

MAX_QUERY_LENGTH = 50
PAGE_SIZE = 50


def normalize_query(raw: str) -> str:
    value = raw.strip()
    if not 1 <= len(value) <= MAX_QUERY_LENGTH:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: q")
    return value


def rank_group(instrument: Instrument, query: str) -> int | None:
    symbol = instrument.symbol.lower()
    needle = query.lower()
    if symbol == needle:
        return 0
    if symbol.startswith(needle):
        return 1
    if needle in instrument.name.lower():
        return 2
    return None


def matches_classification(instrument: Instrument, classification: str | None) -> bool:
    if classification is None:
        return True
    return instrument.classification is Classification(classification)


def search_reference(
    instruments: list[Instrument],
    query: str,
    exchange: str | None = None,
    classification: str | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE,
) -> tuple[list[Instrument], int]:
    ranked: list[tuple[int, str, Instrument]] = []
    for instrument in instruments:
        rank = rank_group(instrument, query)
        if rank is None:
            continue
        if exchange is not None and instrument.exchange != exchange:
            continue
        if not matches_classification(instrument, classification):
            continue
        ranked.append((rank, instrument.symbol, instrument))
    ranked.sort(key=lambda item: (item[0], item[1]))
    start = (page - 1) * page_size
    return [item[2] for item in ranked[start : start + page_size]], len(ranked)
