import pytest

from app.domain.errors import DomainError
from app.domain.statuses import BookingStatus, ensure_transition_allowed


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BookingStatus.PENDING, BookingStatus.CONFIRMED),
        (BookingStatus.PENDING, BookingStatus.CANCELLED_BY_ADMIN),
        (BookingStatus.PENDING, BookingStatus.CANCELLED_BY_CUSTOMER),
        (BookingStatus.CONFIRMED, BookingStatus.COMPLETED),
        (BookingStatus.CONFIRMED, BookingStatus.NO_SHOW),
        (BookingStatus.CONFIRMED, BookingStatus.CANCELLED_BY_ADMIN),
        (BookingStatus.CONFIRMED, BookingStatus.CANCELLED_BY_CUSTOMER),
    ],
)
def test_allowed_status_transitions(current: BookingStatus, target: BookingStatus) -> None:
    ensure_transition_allowed(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BookingStatus.COMPLETED, BookingStatus.CONFIRMED),
        (BookingStatus.NO_SHOW, BookingStatus.CONFIRMED),
        (BookingStatus.CANCELLED_BY_ADMIN, BookingStatus.CONFIRMED),
        (BookingStatus.CANCELLED_BY_CUSTOMER, BookingStatus.CONFIRMED),
    ],
)
def test_terminal_statuses_cannot_transition(current: BookingStatus, target: BookingStatus) -> None:
    with pytest.raises(DomainError):
        ensure_transition_allowed(current, target)


def test_active_capacity_statuses() -> None:
    assert BookingStatus.PENDING.occupies_capacity is True
    assert BookingStatus.CONFIRMED.occupies_capacity is True
    assert BookingStatus.COMPLETED.occupies_capacity is False
