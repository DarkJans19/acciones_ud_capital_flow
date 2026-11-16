from acciones_ud.shared.infrastructure.periodic_job import PeriodicJob


class ReportSchedulerJob(PeriodicJob):
    """MOD-05 scheduler lifecycle with isolated cycles and clean asyncio cancellation."""
