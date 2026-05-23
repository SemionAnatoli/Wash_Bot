class DomainError(Exception):
    """Base error for expected domain failures."""


class BookingSlotUnavailableError(DomainError):
    """Raised when a booking slot is no longer available."""


class ActiveBookingAlreadyExistsError(DomainError):
    """Raised when a Telegram customer already has an active future booking."""


class CancellationTooLateError(DomainError):
    """Raised when a booking can no longer be cancelled by the customer."""


class ValidationError(DomainError):
    """Raised when user-provided input is invalid."""
