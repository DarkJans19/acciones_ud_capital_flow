import asyncio

from acciones_ud.orders.adapters.inbound.jobs.order_reconcile_job import OrderReconcileJob
from acciones_ud.orders.adapters.inbound.jobs.order_scheduler_job import OrderSchedulerJob


async def test_jobs_stop_while_work_is_waiting() -> None:
    class Work:
        def __init__(self) -> None:
            self.entered, self.released = asyncio.Event(), asyncio.Event()

        async def run_once(self) -> None:
            self.entered.set()
            await self.released.wait()

    for kind in (OrderReconcileJob, OrderSchedulerJob):
        work = Work()
        job = kind(work, 30, "orders-test")
        job.start()
        task = job.task
        await asyncio.wait_for(work.entered.wait(), 1)
        await job.stop()
        assert task.done() and job.task is None
        await job.stop()
