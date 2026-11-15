from acciones_ud.shared.infrastructure.periodic_job import PeriodicJob


class OrderReconcileJob(PeriodicJob):
    """Periodic execution reconciliation with cancellation-safe shutdown."""
