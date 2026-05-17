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
    if slot_step <= timedelta(0):
        raise ValueError("Slot step must be positive.")
    if duration <= timedelta(0):
        raise ValueError("Duration must be positive.")
    if bay_count <= 0:
        raise ValueError("Bay count must be positive.")

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
    events: list[tuple[datetime, int]] = []
    for booking in bookings:
        if not intervals_overlap(start, end, booking.start, booking.end):
            continue

        clipped_start = max(booking.start, start)
        clipped_end = min(booking.end, end)
        if clipped_start >= clipped_end:
            continue

        events.append((clipped_start, 1))
        events.append((clipped_end, -1))

    occupied = 0
    peak_occupied = 0
    for _, delta in sorted(events, key=lambda event: (event[0], event[1])):
        occupied += delta
        peak_occupied = max(peak_occupied, occupied)

    return peak_occupied < bay_count


def _not_blocked(start: datetime, end: datetime, blocked: list[BlockedInterval]) -> bool:
    return not any(intervals_overlap(start, end, item.start, item.end) for item in blocked)
