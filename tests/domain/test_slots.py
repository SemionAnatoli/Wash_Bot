from datetime import datetime, time, timedelta

from app.domain.slots import BookingInterval, BlockedInterval, generate_available_slots


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
