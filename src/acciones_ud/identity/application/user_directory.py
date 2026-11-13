"""Administrative user directory use cases (Requirements 20 and 21)."""

from uuid import UUID

from acciones_ud.identity.domain.admin_ports import DirectoryWorkFactory
from acciones_ud.identity.domain.directory import DirectoryEntry, DirectoryPage, DirectoryQuery
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class UserDirectoryService:
    def __init__(self, uow: DirectoryWorkFactory, clock: Clock) -> None:
        self.uow, self.clock = uow, clock

    async def list(self, query: DirectoryQuery) -> DirectoryPage:
        async with self.uow() as work:
            return await work.directory.search(query, self.clock.now())

    async def detail(self, user_id: UUID) -> DirectoryEntry:
        async with self.uow() as work:
            entry = await work.directory.get(user_id, self.clock.now())
        if entry is None:
            raise AppError(
                404, ErrorCode.NOT_FOUND, "User not found.", {"resource": "user"}
            )
        return entry
