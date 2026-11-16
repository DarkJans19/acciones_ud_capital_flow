import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.domain.entities import ProposalAction as A
from acciones_ud.brokers.domain.entities import ProposalStatus as S
from acciones_ud.brokers.domain.errors import InvalidProposalStateError
from acciones_ud.brokers.domain.proposal_state_machine import transition


# Feature: brokers-mod-06, Property 7: Tabla de transiciones de la Proposal
@settings(max_examples=100)
@given(st.sampled_from(list(S)), st.sampled_from(list(A)))
def test_proposal_transition_model(current, action):
    targets = {
        S.SENT: {
            A.MODIFY: S.SENT,
            A.ACCEPT: S.ACCEPTED,
            A.REJECT: S.REJECTED,
            A.WITHDRAW: S.WITHDRAWN,
            A.EXPIRE: S.EXPIRED,
        },
        S.ACCEPTED: {
            A.MODIFY: S.SENT,
            A.WITHDRAW: S.WITHDRAWN,
            A.APPROVE: S.APPROVED,
            A.DECLINE: S.DECLINED_BY_BROKER,
            A.CONVERSION_FAIL: S.CONVERSION_FAILED,
        },
    }
    expected = targets.get(current, {}).get(action)
    if expected is not None:
        assert transition(current, action) == expected
    else:
        with pytest.raises(InvalidProposalStateError) as caught:
            transition(current, action)
        assert caught.value.details == {"current_status": current}
