"""RF-26 / Property 25: notification channel selection."""

from collections.abc import Iterable

from acciones_ud.market_data.domain.entities import CHANNELS

IN_APP = "in_app"
EXTERNAL_CHANNELS = tuple(channel for channel in CHANNELS if channel != IN_APP)


class NoDestinationError(Exception):
    """A recipient lacks the address for an enabled external channel.

    A channel sender raises this before any network call. The Notifier maps it
    to a ``no_destination`` delivery failure instead of the generic
    ``sender_error`` code, so dispatch never crashes (14.18).
    """


def channels_for(
    preferences: Iterable[tuple[str, str, bool]], event_type: str
) -> set[str]:
    selected = {IN_APP}
    for candidate_event, channel, enabled in preferences:
        if candidate_event == event_type and channel in EXTERNAL_CHANNELS and enabled:
            selected.add(channel)
    return selected
