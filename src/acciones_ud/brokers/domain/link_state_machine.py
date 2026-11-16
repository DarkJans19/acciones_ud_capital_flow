from datetime import datetime, timedelta

from acciones_ud.brokers.domain.entities import Link, LinkAction, LinkStatus
from acciones_ud.brokers.domain.errors import InvalidLinkStateError

ALLOWED = {
    (LinkStatus.REQUESTED, LinkAction.ACCEPT): LinkStatus.ACTIVE,
    (LinkStatus.REQUESTED, LinkAction.DECLINE): LinkStatus.DECLINED,
    (LinkStatus.REQUESTED, LinkAction.CANCEL): LinkStatus.CANCELED,
    (LinkStatus.REQUESTED, LinkAction.EXPIRE): LinkStatus.EXPIRED,
    (LinkStatus.ACTIVE, LinkAction.END): LinkStatus.ENDED,
}
ACTORS = {
    LinkAction.ACCEPT: "broker",
    LinkAction.DECLINE: "broker",
    LinkAction.CANCEL: "investor",
    LinkAction.END: "investor",
    LinkAction.EXPIRE: "system",
}


def transition(current: LinkStatus, action: LinkAction) -> LinkStatus:
    target = ALLOWED.get((current, action))
    if target is None:
        raise InvalidLinkStateError(current)
    return target


def is_open(status: LinkStatus) -> bool:
    return status in {LinkStatus.REQUESTED, LinkStatus.ACTIVE}


def is_terminal(status: LinkStatus) -> bool:
    return not is_open(status)


def effective_status(link: Link, now: datetime, ttl_days: int) -> LinkStatus:
    if link.status == LinkStatus.REQUESTED and now >= link.requested_at + timedelta(days=ttl_days):
        return LinkStatus.EXPIRED
    return link.status


def actor_allowed(action: LinkAction, actor_role: str) -> bool:
    return ACTORS.get(action) == actor_role
