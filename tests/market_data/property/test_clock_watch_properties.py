# Feature: identity-market-backend, Property 28: Clock watcher emits events on transitions

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.clock_watch import transitions

OBSERVATIONS = st.lists(st.one_of(st.none(), st.booleans()), max_size=40)


def reference(observations: list[bool | None]) -> list[str]:
    events: list[str] = []
    previous: bool | None = None
    seen = False
    for observed in observations:
        if observed is None:
            continue
        if not seen:
            previous, seen = observed, True
            continue
        if observed is True and previous is False:
            events.append("market_open")
        elif observed is False and previous is True:
            events.append("market_close")
        previous = observed
    return events


@given(OBSERVATIONS)
def test_clock_watcher_emits_exactly_on_transitions(
    observations: list[bool | None],
) -> None:
    assert transitions(observations) == reference(observations)
