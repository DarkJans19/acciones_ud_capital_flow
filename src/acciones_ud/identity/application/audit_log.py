"""Audit_Log read use case (Requirement 25.7, D11)."""

from acciones_ud.identity.domain.admin_ports import AdminWorkFactory
from acciones_ud.identity.domain.audit import AuditPage, AuditQuery


class AuditLogService:
    def __init__(self, uow: AdminWorkFactory) -> None:
        self.uow = uow

    async def list(self, query: AuditQuery) -> AuditPage:
        async with self.uow() as work:
            return await work.audit.search(query)
