import asyncio

from acciones_ud.portfolio.adapters.inbound.jobs.report_scheduler_job import ReportSchedulerJob


async def test_job_cancels_in_flight_cycle():
    entered = asyncio.Event()
    stopped = asyncio.Event()

    class Work:
        async def run_once(self):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

    job = ReportSchedulerJob(Work(), 900, "portfolio-report")
    job.start()
    await asyncio.wait_for(entered.wait(), 1)
    task = job.task
    await job.stop()
    assert stopped.is_set() and task.done() and job.task is None
