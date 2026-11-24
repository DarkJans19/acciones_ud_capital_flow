from dataclasses import asdict
from datetime import date, datetime, time
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence.tables import admin_audit_log
from acciones_ud.shared.domain.audit_entry import AuditRecord


def _json(value: Any) -> Any:
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    return value


class ScheduleAuditWriter:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, record: AuditRecord) -> None:
        values = asdict(record)
        values["payload"] = _json(record.payload)
        await self.session.execute(sa.insert(admin_audit_log).values(**values))
