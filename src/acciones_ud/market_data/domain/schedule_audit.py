from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from acciones_ud.shared.domain.audit_entry import AuditRecord, RequestMeta, build_record


@dataclass(frozen=True)
class AuditActor:
    user_id: UUID
    meta: RequestMeta = RequestMeta()


class ScheduleAuditWriter(Protocol):
    async def append(self, record: AuditRecord) -> None: ...


class ScheduleChangeListener(Protocol):
    def changed(self, entry_id: UUID) -> None: ...


def build(
    action: str,
    actor: AuditActor,
    market: str,
    override: UUID | None,
    day: date,
    before: Any,
    after: Any,
    at: datetime,
) -> AuditRecord:
    keys = frozenset({"override_id", "effective_from", "before", "after"})
    return build_record(
        action,
        keys,
        actor.user_id,
        "market",
        market,
        {"override_id": override, "effective_from": day, "before": before, "after": after},
        at,
        actor.meta,
    )
