from acciones_ud.shared.infrastructure.periodic_job import PeriodicJob


class TransferReconcileJob(PeriodicJob):
    """The lifecycle is shared; TransferReconciler supplies the MOD-04 work."""
