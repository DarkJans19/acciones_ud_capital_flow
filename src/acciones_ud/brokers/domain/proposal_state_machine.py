from datetime import datetime, timedelta

from acciones_ud.brokers.domain.entities import Proposal
from acciones_ud.brokers.domain.entities import ProposalAction as A
from acciones_ud.brokers.domain.entities import ProposalStatus as S
from acciones_ud.brokers.domain.errors import (
    InvalidProposalStateError,
    ProposalVersionConflictError,
)

ALLOWED = {
    (S.SENT, A.MODIFY): S.SENT,
    (S.ACCEPTED, A.MODIFY): S.SENT,
    (S.SENT, A.ACCEPT): S.ACCEPTED,
    (S.SENT, A.REJECT): S.REJECTED,
    (S.SENT, A.WITHDRAW): S.WITHDRAWN,
    (S.ACCEPTED, A.WITHDRAW): S.WITHDRAWN,
    (S.ACCEPTED, A.APPROVE): S.APPROVED,
    (S.ACCEPTED, A.DECLINE): S.DECLINED_BY_BROKER,
    (S.ACCEPTED, A.CONVERSION_FAIL): S.CONVERSION_FAILED,
    (S.SENT, A.EXPIRE): S.EXPIRED,
}


def transition(current: S, action: A) -> S:
    target = ALLOWED.get((current, action))
    if target is None:
        raise InvalidProposalStateError(current)
    return target


def check_version(current_version: int, seen_version: int) -> None:
    if current_version != seen_version:
        raise ProposalVersionConflictError(current_version)


def effective_status(proposal: Proposal, now: datetime, ttl_hours: int) -> S:
    if proposal.status == S.SENT and now >= proposal.last_version_at + timedelta(hours=ttl_hours):
        return S.EXPIRED
    return proposal.status
