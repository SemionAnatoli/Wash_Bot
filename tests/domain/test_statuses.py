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


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BookingStatus.PENDING, BookingStatus.COMPLETED),
        (BookingStatus.PENDING, BookingStatus.NO_SHOW),
        (BookingStatus.CONFIRMED, BookingStatus.PENDING),
    ],
)
def test_active_statuses_reject_invalid_transitions(
    current: BookingStatus, target: BookingStatus
) -> None:
    with pytest.raises(DomainError):
        ensure_transition_allowed(current, target)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (BookingStatus.PENDING, True),
        (BookingStatus.CONFIRMED, True),
        (BookingStatus.CANCELLED_BY_CUSTOMER, False),
        (BookingStatus.CANCELLED_BY_ADMIN, False),
        (BookingStatus.COMPLETED, False),
        (BookingStatus.NO_SHOW, False),
    ],
)
def test_capacity_statuses(status: BookingStatus, expected: bool) -> None:
    assert status.occupies_capacity is expected
