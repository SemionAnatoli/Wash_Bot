class DomainError(Exception):
    """Base error for expected domain failures."""


class BookingSlotUnavailableError(DomainError):
    """Raised when a booking slot is no longer available."""


class ValidationError(DomainError):
    """Raised when user-provided input is invalid."""
