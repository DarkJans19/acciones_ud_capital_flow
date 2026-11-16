from acciones_ud.shared.infrastructure.periodic_job import PeriodicJob


class ExpiryJob(PeriodicJob):
    """RF-13/RF-18: retry failed cycles and cancel cleanly on application shutdown."""
