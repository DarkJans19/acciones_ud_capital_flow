from datetime import datetime
from uuid import UUID

import sqlalchemy as sa

from acciones_ud.admin.domain.audit import sanitize
from acciones_ud.admin.domain.errors import invalid
from acciones_ud.admin.domain.model import BehaviorEvent, Raw
from acciones_ud.admin.domain.pagination import decode, encode


class AuditTrailReader:
    async def page(
        self, start: datetime, end: datetime, filters: Raw, cursor: str | None, size: int
    ) -> Raw:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        if not 1 <= size <= 100:
            raise invalid("page_size")
        if filters.get("source") not in {None, "admin", "orders", "brokers", "auth"}:
            raise invalid("source")
        conditions = ["occurred_at >= :start", "occurred_at < :end"]
        params: Raw = {"start": start, "end": end, "limit": size + 1}
        for name in ("source", "action", "entity_type", "entity_id"):
            if filters.get(name) is not None:
                conditions.append(f"{name} = :{name}")
                params[name] = filters[name]
        if filters.get("user_id"):
            conditions.append(
                "(actor_id = :user_id OR subject_user_id = :user_id OR related_user_id = :user_id)"
            )
            params["user_id"] = filters["user_id"]
        if cursor:
            raw_at, source, ident = decode(cursor, 3)
            try:
                at = datetime.fromisoformat(raw_at)
                if at.utcoffset() is None:
                    raise ValueError()
            except ValueError:
                raise invalid("cursor") from None
            conditions.append("(occurred_at,source,event_id) < (:at,:last_source,:last_id)")
            params.update(at=at, last_source=source, last_id=ident)
        statement = sa.text(
            "SELECT * FROM audit_trail WHERE "
            + " AND ".join(conditions)
            + " ORDER BY occurred_at DESC,source DESC,event_id DESC LIMIT :limit"
        )
        async with unit_of_work() as session:
            rows = [dict(row) for row in (await session.execute(statement, params)).mappings()]
        selected = rows[:size]
        return {
            "items": sanitize(selected),
            "next_cursor": encode(
                (
                    selected[-1]["occurred_at"].isoformat(),
                    selected[-1]["source"],
                    selected[-1]["event_id"],
                )
            )
            if len(rows) > size
            else None,
        }

    async def counts(self, user: UUID, start: datetime, end: datetime) -> list[Raw]:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        async with unit_of_work() as session:
            result = await session.execute(
                sa.text("""SELECT source,action,count(*) AS count
                FROM audit_trail WHERE occurred_at >= :start AND occurred_at < :end AND
                (actor_id = :user OR subject_user_id = :user OR related_user_id = :user)
                GROUP BY source,action ORDER BY source,action"""),
                {"start": start, "end": end, "user": user},
            )
            return [dict(row) for row in result.mappings()]

    async def order_custody(self, order_id: UUID) -> Raw | None:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        async with unit_of_work() as session:
            row = (
                (
                    await session.execute(
                        sa.text("SELECT * FROM orders WHERE id = :id"), {"id": order_id}
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            result: Raw = {"order": dict(row)}
            for key, table, ordering in (
                ("events", "order_events", "at,id"),
                ("executions", "order_executions", "executed_at,alpaca_execution_id"),
                ("cancel_requests", "order_cancel_requests", "requested_at,id"),
                ("reauthorizations", "order_reauthorizations", "deadline,id"),
            ):
                rows = await session.execute(
                    sa.text(f"SELECT * FROM {table} WHERE order_id = :id ORDER BY {ordering}"),
                    {"id": order_id},
                )
                result[key] = [dict(r) for r in rows.mappings()]
            proposals = await session.execute(
                sa.text(
                    "SELECT id,broker_id,investor_id,accepted_version FROM broker_proposals "
                    "WHERE order_id = :id"
                ),
                {"id": order_id},
            )
            result["proposals"] = [dict(r) for r in proposals.mappings()]
        events = result["events"]
        created = next((e for e in events if e["from_status"] is None), None)
        signed = next(
            (
                e
                for e in events
                if e["to_status"] == "BROKER_SIGNED" and e["actor_type"] == "broker"
            ),
            None,
        )
        sent = next((e for e in events if e["to_status"] == "SUBMITTED"), None)
        result.update(
            created_by=created["actor_id"] if created else None,
            authorization_method=created["metadata"].get("authorization_method")
            if created
            else None,
            signed_by=signed["actor_id"] if signed else None,
            signed_at=signed["at"] if signed else None,
            first_submitted_at=sent["at"] if sent else None,
        )
        return dict(sanitize(result))

    async def behavior(self, start: datetime, end: datetime) -> list[BehaviorEvent]:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        async with unit_of_work() as session:
            result = await session.execute(
                sa.text("""SELECT e.id::text,e.order_id,
                o.user_id,e.at,e.from_status,e.to_status,e.cause FROM order_events e
                JOIN orders o ON o.id = e.order_id WHERE e.at >= :start AND e.at < :end
                AND (e.from_status IS NULL OR (e.to_status IN
                  ('CANCELED','REJECTED','FAILED','EXECUTING')
                  AND e.from_status IS DISTINCT FROM e.to_status))"""),
                {"start": start, "end": end},
            )
            values = []
            for row in result.mappings():
                if row["from_status"] is None:
                    kind = "created"
                else:
                    kind = {
                        "CANCELED": "canceled",
                        "REJECTED": "rejected",
                        "FAILED": "failed",
                        "EXECUTING": "accepted",
                    }[row["to_status"]]
                # Only known user/business rejection codes enter a rejection streak.
                business = row["cause"] in {
                    "ORDER_REJECTED",
                    "INSUFFICIENT_BUYING_POWER",
                    "INSUFFICIENT_POSITION",
                    "ASSET_NOT_TRADABLE",
                    "VALIDATION_ERROR",
                    "DAILY_ORDER_LIMIT_REACHED",
                }
                values.append(
                    BehaviorEvent(
                        row["id"], row["user_id"], row["order_id"], row["at"], kind, business
                    )
                )
            return values
