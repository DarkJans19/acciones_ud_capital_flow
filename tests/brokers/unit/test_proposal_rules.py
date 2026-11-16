import pytest

from acciones_ud.brokers.domain.entities import ProposalAction as A
from acciones_ud.brokers.domain.entities import ProposalStatus as S
from acciones_ud.brokers.domain.errors import (
    InvalidProposalStateError,
    ProposalVersionConflictError,
)
from acciones_ud.brokers.domain.proposal_state_machine import check_version, transition


def test_conversion_failure_and_version_conflict():
    assert transition(S.ACCEPTED, A.CONVERSION_FAIL) == S.CONVERSION_FAILED
    with pytest.raises(InvalidProposalStateError):
        transition(S.APPROVED, A.CONVERSION_FAIL)
    with pytest.raises(ProposalVersionConflictError):
        check_version(2, 1)
