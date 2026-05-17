from dataclasses import dataclass
from datetime import datetime, time, timedelta

from app.domain.time import intervals_overlap


@dataclass(frozen=True, slots=True)
class BookingInterval:
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class BlockedInterval:
    start: datetime
    end: datetime


def generate_available_slots(
    *,
    day: datetime,
    work_start: time,
    work_end: time,
    duration: timedelta,
    slot_step: timedelta,
    bay_count: int,
    bookings: list[BookingInterval],
    blocked: list[BlockedInterval],
) -> list[datetime]:
    work_start_at = datetime.combine(day.date(), work_start)
    work_end_at = datetime.combine(day.date(), work_end)
    slots: list[datetime] = []

    candidate = work_start_at
    while candidate + duration <= work_end_at:
        candidate_end = candidate + duration
        if _fits_capacity(candidate, candidate_end, bay_count, bookings) and _not_blocked(
            candidate,
            candidate_end,
            blocked,
        ):
            slots.append(candidate)
        candidate += slot_step

    return slots


def _fits_capacity(
    start: datetime,
    end: datetime,
    bay_count: int,
    bookings: list[BookingInterval],
) -> bool:
    overlapping = sum(
        1 for booking in bookings if intervals_overlap(start, end, booking.start, booking.end)
    )
    return overlapping < bay_count


def _not_blocked(start: datetime, end: datetime, blocked: list[BlockedInterval]) -> bool:
    return not any(intervals_overlap(start, end, item.start, item.end) for item in blocked)
