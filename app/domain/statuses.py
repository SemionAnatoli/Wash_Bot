from enum import StrEnum

from app.domain.errors import DomainError


class BookingStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED_BY_CUSTOMER = "cancelled_by_customer"
    CANCELLED_BY_ADMIN = "cancelled_by_admin"
    COMPLETED = "completed"
    NO_SHOW = "no_show"

    @property
    def occupies_capacity(self) -> bool:
        return self in {BookingStatus.PENDING, BookingStatus.CONFIRMED}


_ALLOWED_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.PENDING: {
        BookingStatus.CONFIRMED,
        BookingStatus.CANCELLED_BY_ADMIN,
        BookingStatus.CANCELLED_BY_CUSTOMER,
    },
    BookingStatus.CONFIRMED: {
        BookingStatus.COMPLETED,
        BookingStatus.NO_SHOW,
        BookingStatus.CANCELLED_BY_ADMIN,
        BookingStatus.CANCELLED_BY_CUSTOMER,
    },
    BookingStatus.CANCELLED_BY_CUSTOMER: set(),
    BookingStatus.CANCELLED_BY_ADMIN: set(),
    BookingStatus.COMPLETED: set(),
    BookingStatus.NO_SHOW: set(),
}


def ensure_transition_allowed(current: BookingStatus, target: BookingStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise DomainError(f"Cannot transition booking from {current} to {target}.")
