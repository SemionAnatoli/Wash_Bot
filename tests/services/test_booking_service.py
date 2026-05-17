from datetime import datetime

import pytest

from app.domain.errors import DomainError, ValidationError
from app.domain.statuses import BookingStatus
from app.services.booking_service import (
    BookingCapacity,
    CreateBookingCommand,
    ensure_booking_can_be_created,
)


def test_create_booking_command_keeps_requested_interval() -> None:
    command = CreateBookingCommand(
        car_wash_id=1,
        branch_id=1,
        customer_id=1,
        main_service_id=10,
        addon_service_ids=[11, 12],
        start_at=datetime(2026, 5, 18, 12, 0),
        total_duration_minutes=90,
        confirmation_status=BookingStatus.CONFIRMED,
    )

    assert command.end_at == datetime(2026, 5, 18, 13, 30)


def test_create_booking_command_rejects_non_positive_duration() -> None:
    command = CreateBookingCommand(
        car_wash_id=1,
        branch_id=1,
        customer_id=1,
        main_service_id=10,
        addon_service_ids=[],
        start_at=datetime(2026, 5, 18, 12, 0),
        total_duration_minutes=0,
        confirmation_status=BookingStatus.CONFIRMED,
    )

    with pytest.raises(ValidationError):
        _ = command.end_at


def test_ensure_booking_can_be_created_allows_remaining_capacity() -> None:
    capacity = BookingCapacity(
        bay_count=2,
        overlapping_bookings=1,
        overlapping_blocks=0,
    )

    ensure_booking_can_be_created(capacity)


@pytest.mark.parametrize("bay_count", [0, -1])
def test_ensure_booking_can_be_created_rejects_non_positive_bay_count(
    bay_count: int,
) -> None:
    capacity = BookingCapacity(
        bay_count=bay_count,
        overlapping_bookings=0,
        overlapping_blocks=0,
    )

    with pytest.raises(ValidationError):
        ensure_booking_can_be_created(capacity)


def test_ensure_booking_can_be_created_rejects_negative_overlapping_bookings() -> None:
    capacity = BookingCapacity(
        bay_count=2,
        overlapping_bookings=-1,
        overlapping_blocks=0,
    )

    with pytest.raises(ValidationError):
        ensure_booking_can_be_created(capacity)


def test_ensure_booking_can_be_created_rejects_negative_overlapping_blocks() -> None:
    capacity = BookingCapacity(
        bay_count=2,
        overlapping_bookings=0,
        overlapping_blocks=-1,
    )

    with pytest.raises(ValidationError):
        ensure_booking_can_be_created(capacity)


def test_ensure_booking_can_be_created_rejects_full_capacity() -> None:
    capacity = BookingCapacity(
        bay_count=2,
        overlapping_bookings=2,
        overlapping_blocks=0,
    )

    with pytest.raises(DomainError):
        ensure_booking_can_be_created(capacity)


def test_ensure_booking_can_be_created_rejects_blocked_time() -> None:
    capacity = BookingCapacity(
        bay_count=2,
        overlapping_bookings=0,
        overlapping_blocks=1,
    )

    with pytest.raises(DomainError):
        ensure_booking_can_be_created(capacity)
