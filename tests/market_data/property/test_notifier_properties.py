# Feature: identity-market-backend, Property 25: Notification channel selection

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.entities import CHANNELS, EVENT_TYPES
from acciones_ud.market_data.domain.notifications import EXTERNAL_CHANNELS, channels_for

PREFERENCES = st.lists(
    st.tuples(st.sampled_from(EVENT_TYPES), st.sampled_from(CHANNELS), st.booleans()),
    max_size=28,
)


@given(preferences=PREFERENCES, event_type=st.sampled_from(EVENT_TYPES))
def test_channel_selection(
    preferences: list[tuple[str, str, bool]], event_type: str
) -> None:
    selected = channels_for(preferences, event_type)

    assert "in_app" in selected
    for candidate_event, channel, enabled in preferences:
        if candidate_event == event_type and channel in EXTERNAL_CHANNELS and enabled:
            assert channel in selected
    for channel in selected - {"in_app"}:
        assert any(
            candidate_event == event_type and candidate == channel and enabled
            for candidate_event, candidate, enabled in preferences
        )


@given(preferences=PREFERENCES)
def test_only_the_selected_event_type_is_considered(
    preferences: list[tuple[str, str, bool]],
) -> None:
    for event_type in EVENT_TYPES:
        selection = channels_for(preferences, event_type)
        if not any(
            candidate == event_type and channel in EXTERNAL_CHANNELS and enabled
            for candidate, channel, enabled in preferences
        ):
            assert selection == {"in_app"}
