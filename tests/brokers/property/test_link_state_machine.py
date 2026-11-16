import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.domain.entities import LinkAction as A
from acciones_ud.brokers.domain.entities import LinkStatus as S
from acciones_ud.brokers.domain.errors import InvalidLinkStateError
from acciones_ud.brokers.domain.link_state_machine import (
    actor_allowed,
    is_open,
    is_terminal,
    transition,
)


# Feature: brokers-mod-06, Property 1: Tabla de transiciones de la Link
@settings(max_examples=100)
@given(
    st.sampled_from(list(S)),
    st.sampled_from(list(A)),
    st.sampled_from(["broker", "investor", "system"]),
)
def test_link_transition_model(current, action, actor):
    targets = {
        (S.REQUESTED, A.ACCEPT): (S.ACTIVE, "broker"),
        (S.REQUESTED, A.DECLINE): (S.DECLINED, "broker"),
        (S.REQUESTED, A.CANCEL): (S.CANCELED, "investor"),
        (S.REQUESTED, A.EXPIRE): (S.EXPIRED, "system"),
        (S.ACTIVE, A.END): (S.ENDED, "investor"),
    }
    expected = targets.get((current, action))
    assert is_terminal(current) == (current not in {S.REQUESTED, S.ACTIVE})
    assert is_open(current) != is_terminal(current)
    if expected:
        assert transition(current, action) == expected[0]
        assert actor_allowed(action, actor) == (actor == expected[1])
    else:
        with pytest.raises(InvalidLinkStateError) as caught:
            transition(current, action)
        assert caught.value.details == {"current_status": current}
