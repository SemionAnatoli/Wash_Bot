from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.errors import DomainError, ValidationError
from app.domain.statuses import BookingStatus


@dataclass(frozen=True, slots=True)
class CreateBookingCommand:
    car_wash_id: int
    branch_id: int
    customer_id: int
    main_service_id: int
    addon_service_ids: list[int]
    start_at: datetime
    total_duration_minutes: int
    confirmation_status: BookingStatus

    @property
    def end_at(self) -> datetime:
        if self.total_duration_minutes <= 0:
            raise ValidationError("Booking duration must be positive.")
        return self.start_at + timedelta(minutes=self.total_duration_minutes)


@dataclass(frozen=True, slots=True)
class BookingCapacity:
    bay_count: int
    overlapping_bookings: int
    overlapping_blocks: int


def ensure_booking_can_be_created(capacity: BookingCapacity) -> None:
    if capacity.bay_count <= 0:
        raise ValidationError("Branch must have at least one bay.")
    if capacity.overlapping_bookings < 0:
        raise ValidationError("Overlapping booking count cannot be negative.")
    if capacity.overlapping_blocks < 0:
        raise ValidationError("Overlapping block count cannot be negative.")
    if capacity.overlapping_blocks > 0:
        raise DomainError("Cannot create booking during blocked time.")
    if capacity.overlapping_bookings >= capacity.bay_count:
        raise DomainError("Cannot create booking because capacity is full.")
