from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence import tables as t
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def missing(resource: str) -> AppError:
    return AppError(404, ErrorCode.NOT_FOUND, "Resource not found.", {"resource": resource})


class RbacRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def user(self, user_id: UUID) -> Record:
        row = (
            (await self.session.execute(sa.select(t.users).where(t.users.c.id == user_id)))
            .mappings()
            .first()
        )
        if not row:
            raise missing("user")
        return dict(row)

    async def assignments(self, user_id: UUID | None = None) -> list[Record]:
        query = sa.select(t.role_assignments, t.users.c.account_status).join(
            t.users, t.role_assignments.c.user_id == t.users.c.id
        )
        if user_id:
            query = query.where(t.role_assignments.c.user_id == user_id)
        return [dict(r) for r in (await self.session.execute(query)).mappings().all()]

    async def roles(self) -> list[Record]:
        rows = (
            await self.session.execute(
                sa.select(t.roles.c.code, t.role_permissions.c.permission_code)
                .outerjoin(t.role_permissions, t.roles.c.code == t.role_permissions.c.role_code)
                .order_by(t.roles.c.code, t.role_permissions.c.permission_code)
            )
        ).all()
        result: dict[str, list[str]] = {}
        for role, permission in rows:
            result.setdefault(str(role), [])
            if permission:
                result[str(role)].append(str(permission))
        return [{"role": role, "permissions": permissions} for role, permissions in result.items()]

    async def permissions(self) -> list[Record]:
        return [
            dict(r)
            for r in (
                await self.session.execute(sa.select(t.permissions).order_by(t.permissions.c.code))
            )
            .mappings()
            .all()
        ]

    async def lock_admin_guard(self) -> None:
        # Stable existing row serializes every administrator assignment change across users.
        await self.session.execute(
            sa.select(t.roles.c.code).where(t.roles.c.code == "administrator").with_for_update()
        )

    async def save_assignment(
        self,
        user_id: UUID,
        role: str,
        valid_from: datetime,
        valid_to: datetime | None,
        assignment_id: UUID | None,
    ) -> Record:
        if not (
            await self.session.execute(sa.select(t.roles.c.code).where(t.roles.c.code == role))
        ).first():
            raise missing("role")
        values = {"role_code": role, "valid_from": valid_from, "valid_to": valid_to}
        statement: sa.Update | sa.Insert
        if assignment_id:
            statement = (
                t.role_assignments.update()
                .where(
                    t.role_assignments.c.id == assignment_id,
                    t.role_assignments.c.user_id == user_id,
                )
                .values(**values)
            )
        else:
            statement = t.role_assignments.insert().values(id=uuid4(), user_id=user_id, **values)
        row = (
            (await self.session.execute(statement.returning(t.role_assignments))).mappings().first()
        )
        if not row:
            raise missing("role_assignment")
        return dict(row)

    async def cancel_assignment(
        self, user_id: UUID, assignment_id: UUID, actor_id: UUID, now: datetime
    ) -> Record:
        row = (
            (
                await self.session.execute(
                    t.role_assignments.update()
                    .where(
                        t.role_assignments.c.id == assignment_id,
                        t.role_assignments.c.user_id == user_id,
                        t.role_assignments.c.status == "ACTIVE",
                    )
                    .values(status="CANCELLED", cancelled_at=now, cancelled_by=actor_id)
                    .returning(t.role_assignments)
                )
            )
            .mappings()
            .one()
        )
        return dict(row)

    async def change_permission(self, role: str, permission: str, remove: bool) -> Record:
        if not (
            await self.session.execute(sa.select(t.roles).where(t.roles.c.code == role))
        ).first():
            raise missing("role")
        if not (
            await self.session.execute(
                sa.select(t.permissions).where(t.permissions.c.code == permission)
            )
        ).first():
            raise missing("permission")
        if remove:
            await self.session.execute(
                t.role_permissions.delete().where(
                    t.role_permissions.c.role_code == role,
                    t.role_permissions.c.permission_code == permission,
                )
            )
        else:
            await self.session.execute(
                insert(t.role_permissions)
                .values(role_code=role, permission_code=permission)
                .on_conflict_do_nothing()
            )
        return next(r for r in await self.roles() if r["role"] == role)

    async def mark_broker_active(self, user_id: UUID, now: datetime) -> None:
        row = (
            await self.session.execute(
                t.users.update()
                .where(
                    t.users.c.id == user_id, t.users.c.account_status == "pending_broker_activation"
                )
                .values(account_status="active", updated_at=now)
                .returning(t.users.c.id)
            )
        ).first()
        if not row:
            await self.user(user_id)
            raise AppError(409, ErrorCode.BROKER_NOT_PENDING, "Broker is not pending activation.")

    async def set_premium(self, user_id: UUID, value: bool) -> Record:
        await self.user(user_id)
        await self.session.execute(
            t.users.update().where(t.users.c.id == user_id).values(is_premium=value)
        )
        return {"user_id": user_id, "is_premium": value}
