class DomainError(Exception):
    """Error esperado producido por una regla de dominio."""


class NotFoundError(DomainError):
    """El recurso solicitado no existe."""
