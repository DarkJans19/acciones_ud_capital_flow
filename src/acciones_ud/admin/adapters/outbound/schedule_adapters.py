import asyncio
import logging
from datetime import date, datetime
from typing import cast
from uuid import UUID

from fastapi import FastAPI, Request

from acciones_ud.admin.application.schedule_change_dispatcher import ScheduleChangeDispatcher
from acciones_ud.admin.domain.model import Raw
from acciones_ud.market_data import composition as market_data
from acciones_ud.orders.application.schedule_change import ScheduleChange, ScheduleChangePort


class OrderScheduleChanges:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def apply(self, entry: Raw, now: datetime) -> int:
        port = cast(ScheduleChangePort, self.app.state.order_schedule_change_port)
        result = await port.apply(
            ScheduleChange(
                entry["id"],
                entry["target_id"],
                date.fromisoformat(entry["payload"]["effective_from"]),
                entry["action"],
            ),
            now,
        )
        if result.already_applied:
            # A process may have died after orders committed but before admin's marker.
            import sqlalchemy as sa

            from acciones_ud.shared.infrastructure.db import unit_of_work

            async with unit_of_work() as session:
                count = await session.scalar(
                    sa.text(
                        "SELECT affected_count FROM order_schedule_changes WHERE change_id = :id"
                    ),
                    {"id": entry["id"]},
                )
            return int(count or 0)
        return len(result.affected_order_ids)


class ScheduleNotifier:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def recipients(self) -> list[UUID]:
        async with market_data.directory_uow() as directory:
            return [r.user_id for r in await directory.recipients("market_schedule_changes")]

    async def notify(self, user_id: UUID, payload: Raw) -> None:
        async with market_data.directory_uow() as directory:
            recipient = await directory.recipient(user_id, "market_schedule_changes")
        if recipient:
            scope = Request({"type": "http", "app": self.app})
            await market_data.notifier(scope).notify(
                [recipient], "market_schedule_changes", payload
            )


class ScheduleListener:
    def __init__(self, dispatcher: ScheduleChangeDispatcher) -> None:
        self.dispatcher = dispatcher
        self.tasks: set[asyncio.Task[None]] = set()

    def changed(self, entry_id: UUID) -> None:
        async def dispatch() -> None:
            try:
                await self.dispatcher.dispatch(entry_id)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Immediate schedule dispatch failed", extra={"change_id": str(entry_id)}
                )

        task = asyncio.create_task(dispatch(), name="admin-schedule-dispatch")
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def stop(self) -> None:
        if self.tasks:
            done, pending = await asyncio.wait(self.tasks, timeout=10)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
