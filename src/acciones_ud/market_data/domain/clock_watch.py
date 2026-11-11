"""RF-27 / Property 28: market clock watcher transitions."""

from collections.abc import Iterable


def transitions(observations: Iterable[bool | None]) -> list[str]:
    events: list[str] = []
    previous: bool | None = None
    for observed in observations:
        if observed is None:
            continue
        if previous is None:
            previous = observed
            continue
        if observed and not previous:
            events.append("market_open")
        elif not observed and previous:
            events.append("market_close")
        previous = observed
    return events


def should_persist(previous: bool | None, current: bool) -> bool:
    return previous is None or previous is not current
