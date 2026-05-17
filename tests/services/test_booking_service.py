from datetime import datetime

from app.domain.statuses import BookingStatus
from app.services.booking_service import CreateBookingCommand


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
