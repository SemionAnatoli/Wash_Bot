from dataclasses import dataclass
from datetime import datetime, timedelta

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
        return self.start_at + timedelta(minutes=self.total_duration_minutes)
