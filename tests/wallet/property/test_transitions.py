from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.wallet.domain.model import TransferState, TransferUpdate
from acciones_ud.wallet.domain.transfers import decide_update


# Feature: wallet-mod-04, Property 5: Modelo de transición de estados de Transfer
@settings(max_examples=100)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(
                [
                    "PENDING",
                    "QUEUED",
                    "COMPLETE",
                    "CANCELED",
                    "RETURNED",
                    "REJECTED",
                ]
            ),
            st.integers(-1000, 1000),
        ),
        max_size=30,
    )
)
def test_transition_reference(events: list[tuple[str, int]]) -> None:
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    state = TransferState("QUEUED", None)
    expected_status, expected_time = "QUEUED", None
    for status, offset in events:
        at = origin + timedelta(seconds=offset)
        if expected_status not in {"COMPLETE", "CANCELED", "RETURNED", "REJECTED"} and (
            expected_time is None or at > expected_time
        ):
            expected_status, expected_time = status, at
        update = decide_update(state, TransferUpdate(status, at))
        state = update or state
        assert state == TransferState(expected_status, expected_time)
