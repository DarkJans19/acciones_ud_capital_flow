from dataclasses import replace
from datetime import datetime
from uuid import UUID

from acciones_ud.identity.domain.admin_ports import AdminWorkFactory
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.models import AssignmentStatus, RoleAssignment
from acciones_ud.identity.domain.rbac import guard_last_administrator, validate_validity
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def assignment_out(row: Record, now: datetime) -> Record:
    """Shared RoleAssignment view; ``effective`` mirrors the RBAC check (5.7)."""
    return {
        "id": row["id"],
        "role": row["role_code"],
        "valid_from": row["valid_from"],
        "valid_to": row["valid_to"],
        "status": row.get("status", "ACTIVE"),
        "cancelled_at": row.get("cancelled_at"),
        "cancelled_by": row.get("cancelled_by"),
        "effective": row.get("account_status", "active") == "active"
        and row.get("status", "ACTIVE") == "ACTIVE"
        and row["valid_from"] <= now
        and (row["valid_to"] is None or now < row["valid_to"]),
    }


class RbacService:
    def __init__(self, uow: AdminWorkFactory, clock: Clock) -> None:
        self.uow, self.clock = uow, clock

    def assignment_out(self, row: Record) -> Record:
        return assignment_out(row, self.clock.now())

    async def assignments(self, user_id: UUID) -> list[Record]:
        async with self.uow() as work:
            await work.admin.user(user_id)
            return [self.assignment_out(r) for r in await work.admin.assignments(user_id)]

    async def save(
        self,
        user_id: UUID,
        role: str | None,
        start: datetime | None,
        end: datetime | None,
        assignment_id: UUID | None,
        revoke: bool = False,
        actor_id: UUID | None = None,
    ) -> Record:
        now = self.clock.now()
        async with self.uow() as work:
            repo = work.admin
            user = await repo.user(user_id)
            await repo.lock_admin_guard()
            all_rows = await repo.assignments()
            old = next(
                (r for r in all_rows if r["id"] == assignment_id and r["user_id"] == user_id), None
            )
            if assignment_id and old is None:
                raise AppError(
                    404,
                    ErrorCode.NOT_FOUND,
                    "Role assignment not found.",
                    {"resource": "role_assignment"},
                )
            if old:
                if old.get("status") == "CANCELLED":
                    if revoke:
                        return self.assignment_out(old)
                    raise AppError(409, ErrorCode.ASSIGNMENT_CANCELLED, "Assignment is cancelled.")
                if revoke and old["valid_from"] >= now:
                    if actor_id is None:
                        raise AppError(
                            422, ErrorCode.VALIDATION_ERROR, "Cancellation actor required."
                        )
                    before = [
                        RoleAssignment(
                            r["id"],
                            r["user_id"],
                            r["role_code"],
                            r["valid_from"],
                            r["valid_to"],
                            AssignmentStatus(r.get("status", "ACTIVE")),
                        )
                        for r in all_rows
                    ]
                    after = [
                        replace(a, status=AssignmentStatus.CANCELLED)
                        if a.id == assignment_id
                        else a
                        for a in before
                    ]
                    active = {r["user_id"] for r in all_rows if r["account_status"] == "active"}
                    guard_last_administrator(before, after, now, active)
                    result = await repo.cancel_assignment(user_id, old["id"], actor_id, now)
                    return self.assignment_out({**result, "account_status": user["account_status"]})
                role = old["role_code"]
                start = old["valid_from"] if revoke else start
                end = now if revoke else end
            assert role and start
            validate_validity(start, end)
            if old:
                before = [
                    RoleAssignment(
                        r["id"],
                        r["user_id"],
                        r["role_code"],
                        r["valid_from"],
                        r["valid_to"],
                        AssignmentStatus(r.get("status", "ACTIVE")),
                    )
                    for r in all_rows
                ]
                after = [
                    replace(a, valid_from=start, valid_to=end) if a.id == assignment_id else a
                    for a in before
                ]
                active = {r["user_id"] for r in all_rows if r["account_status"] == "active"}
                guard_last_administrator(before, after, now, active)
            result = await repo.save_assignment(user_id, role, start, end, assignment_id)
            return self.assignment_out({**result, "account_status": user["account_status"]})

    async def roles(self) -> list[Record]:
        async with self.uow() as work:
            return await work.admin.roles()

    async def permissions(self) -> list[Record]:
        async with self.uow() as work:
            return await work.admin.permissions()

    async def change_permission(self, role: str, permission: str, remove: bool) -> Record:
        async with self.uow() as work:
            return await work.admin.change_permission(role, permission, remove)

    async def premium(self, user_id: UUID, value: bool) -> Record:
        async with self.uow() as work:
            return await work.admin.set_premium(user_id, value)
