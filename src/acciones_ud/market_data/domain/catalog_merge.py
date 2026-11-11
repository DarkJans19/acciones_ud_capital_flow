"""RF-24: merge the Alpaca asset list into the cached catalog (Property 18)."""

from dataclasses import replace

from acciones_ud.market_data.domain.entities import (
    Instrument,
    InstrumentStatus,
)


def _choose(fetched: list[Instrument]) -> list[Instrument]:
    chosen: dict[str, Instrument] = {}
    order: list[str] = []
    for asset in fetched:
        previous = chosen.get(asset.symbol)
        if previous is None:
            chosen[asset.symbol] = asset
            order.append(asset.symbol)
        elif asset.status == InstrumentStatus.ACTIVE and previous.status != InstrumentStatus.ACTIVE:
            chosen[asset.symbol] = asset
    return [chosen[symbol] for symbol in order]


def merge_catalog(cached: list[Instrument], fetched: list[Instrument]) -> list[Instrument]:
    selected = _choose(fetched)
    by_symbol = {asset.symbol: asset for asset in selected}
    merged: list[Instrument] = []
    for instrument in cached:
        asset = by_symbol.pop(instrument.symbol, None)
        if asset is None:
            merged.append(replace(instrument, listed=False))
        else:
            merged.append(replace(asset, sector=instrument.sector, listed=True))
    for asset in by_symbol.values():
        merged.append(replace(asset, sector=None, listed=True))
    return merged


def merge_asset(cached: list[Instrument], asset: Instrument) -> list[Instrument]:
    return merge_catalog(cached, [asset])
