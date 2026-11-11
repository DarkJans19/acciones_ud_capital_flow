"""RF-26 / Property 25: notification channel selection."""

from collections.abc import Iterable

from acciones_ud.market_data.domain.entities import CHANNELS

IN_APP = "in_app"
EXTERNAL_CHANNELS = tuple(channel for channel in CHANNELS if channel != IN_APP)


def channels_for(
    preferences: Iterable[tuple[str, str, bool]], event_type: str
) -> set[str]:
    selected = {IN_APP}
    for candidate_event, channel, enabled in preferences:
        if candidate_event == event_type and channel in EXTERNAL_CHANNELS and enabled:
            selected.add(channel)
    return selected
