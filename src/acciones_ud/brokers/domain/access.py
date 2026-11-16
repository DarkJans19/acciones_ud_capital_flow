from collections.abc import Iterable, Mapping
from typing import Literal
from uuid import UUID

from acciones_ud.brokers.domain.entities import Link, LinkStatus
from acciones_ud.brokers.domain.errors import NotFoundError

ResourceKind = Literal["link", "proposal", "client"]


def require_active_link(
    link: Link | None, broker_role_active: bool, resource: ResourceKind
) -> Link:
    if link is None or link.status != LinkStatus.ACTIVE or not broker_role_active:
        raise NotFoundError(resource)
    return link


def resolve_link_membership(
    links: Iterable[Link], broker_roles: Mapping[UUID, bool]
) -> dict[UUID, set[UUID]]:
    result: dict[UUID, set[UUID]] = {}
    for link in links:
        if link.status == LinkStatus.ACTIVE and broker_roles.get(link.broker_id, False):
            result.setdefault(link.broker_id, set()).add(link.investor_id)
    return result
