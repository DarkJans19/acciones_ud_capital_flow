"""RF-25 / Properties 19 and 38: snapshot mapping and quote fallback decision."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from acciones_ud.market_data.domain.entities import Snapshot, StoredSnapshot
from acciones_ud.shared.domain.alpaca_errors import AlpacaError, to_app_error


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return None


def _integer(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def instant(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _later(first: datetime | None, second: datetime | None) -> datetime | None:
    present = [value for value in (first, second) if value is not None]
    return max(present) if present else None


def from_snapshot(document: dict[str, Any], feed: str = "iex") -> Snapshot:
    trade = document.get("latestTrade")
    quote = document.get("latestQuote")
    bar = document.get("dailyBar")
    trade_doc = trade if isinstance(trade, dict) else {}
    quote_doc = quote if isinstance(quote, dict) else {}
    bar_doc = bar if isinstance(bar, dict) else {}
    return Snapshot(
        last_trade_price=_decimal(trade_doc.get("p")),
        bid_price=_decimal(quote_doc.get("bp")),
        ask_price=_decimal(quote_doc.get("ap")),
        bid_size=_integer(quote_doc.get("bs")),
        ask_size=_integer(quote_doc.get("as")),
        daily_volume=_integer(bar_doc.get("v")),
        quote_updated_at=_later(
            instant(quote_doc.get("t")),
            instant(trade_doc.get("t")),
        ),
        feed=feed,
    )


def choose_quote(
    live: Snapshot | None,
    stored: StoredSnapshot | None,
    failure: AlpacaError | None,
) -> tuple[Snapshot, bool]:
    if failure is None and live is not None:
        return live, False
    if stored is not None:
        return stored.snapshot, True
    if failure is None:
        raise to_app_error(AlpacaError("Quote unavailable."))
    raise to_app_error(failure)
