from datetime import datetime, time, timedelta

import pytest

from app.domain.slots import (
    BlockedInterval,
    BookingInterval,
    calculate_peak_occupancy,
    generate_available_slots,
)


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 18, hour, minute)


def test_slot_is_available_when_capacity_remains_for_full_interval() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(9, 0),
        work_end=time(12, 0),
        duration=timedelta(minutes=60),
        slot_step=timedelta(minutes=30),
        bay_count=2,
        bookings=[BookingInterval(start=dt(10), end=dt(11))],
        blocked=[],
    )

    assert dt(10) in slots


def test_slot_is_hidden_when_booking_would_overlap_next_booking_at_full_capacity() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(12, 0),
        work_end=time(14, 0),
        duration=timedelta(minutes=90),
        slot_step=timedelta(minutes=30),
        bay_count=1,
        bookings=[BookingInterval(start=dt(13), end=dt(14))],
        blocked=[],
    )

    assert dt(12) not in slots


def test_slot_capacity_uses_peak_occupancy_for_sequential_bookings() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(10, 0),
        work_end=time(12, 0),
        duration=timedelta(minutes=120),
        slot_step=timedelta(minutes=30),
        bay_count=2,
        bookings=[
            BookingInterval(start=dt(10), end=dt(11)),
            BookingInterval(start=dt(11), end=dt(12)),
        ],
        blocked=[],
    )

    assert dt(10) in slots


def test_slot_capacity_blocks_when_peak_occupancy_reaches_bay_count() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(10, 0),
        work_end=time(12, 0),
        duration=timedelta(minutes=120),
        slot_step=timedelta(minutes=30),
        bay_count=2,
        bookings=[
            BookingInterval(start=dt(10), end=dt(12)),
            BookingInterval(start=dt(10, 30), end=dt(11, 30)),
        ],
        blocked=[],
    )

    assert dt(10) not in slots


def test_calculate_peak_occupancy_counts_sequential_bookings_as_one_peak() -> None:
    peak = calculate_peak_occupancy(
        start=dt(10),
        end=dt(12),
        bookings=[
            BookingInterval(start=dt(10), end=dt(11)),
            BookingInterval(start=dt(11), end=dt(12)),
        ],
    )

    assert peak == 1


def test_calculate_peak_occupancy_counts_concurrent_bookings_as_two_peak() -> None:
    peak = calculate_peak_occupancy(
        start=dt(10),
        end=dt(12),
        bookings=[
            BookingInterval(start=dt(10), end=dt(12)),
            BookingInterval(start=dt(10, 30), end=dt(11, 30)),
        ],
    )

    assert peak == 2


def test_slot_is_hidden_when_it_does_not_fit_working_hours() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(9, 0),
        work_end=time(10, 0),
        duration=timedelta(minutes=90),
        slot_step=timedelta(minutes=30),
        bay_count=1,
        bookings=[],
        blocked=[],
    )

    assert slots == []


def test_slot_is_hidden_when_blocked_interval_overlaps() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(9, 0),
        work_end=time(11, 0),
        duration=timedelta(minutes=30),
        slot_step=timedelta(minutes=30),
        bay_count=1,
        bookings=[],
        blocked=[BlockedInterval(start=dt(9, 30), end=dt(10))],
    )

    assert dt(9, 30) not in slots
    assert dt(10) in slots


@pytest.mark.parametrize(
    ("duration", "slot_step", "bay_count"),
    [
        (timedelta(minutes=30), timedelta(0), 1),
        (timedelta(minutes=30), timedelta(minutes=-30), 1),
        (timedelta(0), timedelta(minutes=30), 1),
        (timedelta(minutes=-30), timedelta(minutes=30), 1),
        (timedelta(minutes=30), timedelta(minutes=30), 0),
        (timedelta(minutes=30), timedelta(minutes=30), -1),
    ],
)
def test_slot_generation_rejects_invalid_parameters(
    duration: timedelta,
    slot_step: timedelta,
    bay_count: int,
) -> None:
    with pytest.raises(ValueError):
        generate_available_slots(
            day=datetime(2026, 5, 18),
            work_start=time(9, 0),
            work_end=time(11, 0),
            duration=duration,
            slot_step=slot_step,
            bay_count=bay_count,
            bookings=[],
            blocked=[],
        )
