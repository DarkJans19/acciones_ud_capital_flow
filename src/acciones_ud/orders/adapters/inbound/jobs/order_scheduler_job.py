from acciones_ud.shared.infrastructure.periodic_job import PeriodicJob


class OrderSchedulerJob(PeriodicJob):
    """Periodic scheduling with cancellation-safe shutdown."""
