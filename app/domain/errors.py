class DomainError(Exception):
    """Base error for expected domain failures."""


class ValidationError(DomainError):
    """Raised when user-provided input is invalid."""
