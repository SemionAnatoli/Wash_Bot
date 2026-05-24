from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.admin_booking import (
    AdminBookingActionResult,
    AdminBookingActionStatus,
    AdminBookingDetails,
)
from app.services.customer_booking import ServiceOption


@dataclass
class FakeTelegramUser:
    id: int = 1001
    username: str | None = "admin"


@dataclass
class FakeMessage:
    answers: list[dict[str, Any]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})


@dataclass
class FakeCallbackQuery:
    data: str | None
    message: FakeMessage | None = field(default_factory=FakeMessage)
    from_user: FakeTelegramUser | None = field(default_factory=FakeTelegramUser)
    answered: bool = False

    async def answer(self) -> None:
        self.answered = True


def option(service_id: int, title: str, *, is_addon: bool = False) -> ServiceOption:
    return ServiceOption(
        id=service_id,
        title=title,
        category="addon" if is_addon else "wash",
        price=Decimal("100"),
        duration_minutes=30,
        is_addon=is_addon,
    )


def booking_details(
    *,
    booking_id: int = 15,
    status: str = "pending",
    customer_name: str = "Иван",
) -> AdminBookingDetails:
    return AdminBookingDetails(
        booking_id=booking_id,
        status=status,
        start_at=datetime(2026, 5, 24, 10),
        end_at=datetime(2026, 5, 24, 11),
        customer_name=customer_name,
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
        services=[option(1, "Стандарт")],
    )


@dataclass
class FakeAdminBookingService:
    admin_ids: set[int] = field(default_factory=lambda: {1001})
    today_bookings: list[AdminBookingDetails] = field(default_factory=lambda: [booking_details()])
    confirm_result: AdminBookingActionResult = field(
        default_factory=lambda: AdminBookingActionResult(
            AdminBookingActionStatus.CHANGED,
            booking_details(status="confirmed"),
        )
    )
    cancel_result: AdminBookingActionResult = field(
        default_factory=lambda: AdminBookingActionResult(
            AdminBookingActionStatus.CHANGED,
            booking_details(status="cancelled_by_admin"),
        )
    )
    today_requests: list[dict[str, Any]] = field(default_factory=list)
    confirm_requests: list[dict[str, Any]] = field(default_factory=list)
    cancel_requests: list[dict[str, Any]] = field(default_factory=list)

    def is_admin(self, telegram_user_id: int) -> bool:
        return telegram_user_id in self.admin_ids

    async def list_today_bookings(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        today: date,
    ) -> list[AdminBookingDetails]:
        self.today_requests.append(
            {
                "car_wash_id": car_wash_id,
                "branch_id": branch_id,
                "today": today,
            }
        )
        return self.today_bookings

    async def confirm_booking(
        self,
        *,
        car_wash_id: int,
        booking_id: int,
    ) -> AdminBookingActionResult:
        self.confirm_requests.append({"car_wash_id": car_wash_id, "booking_id": booking_id})
        return self.confirm_result

    async def cancel_booking(
        self,
        *,
        car_wash_id: int,
        booking_id: int,
    ) -> AdminBookingActionResult:
        self.cancel_requests.append({"car_wash_id": car_wash_id, "booking_id": booking_id})
        return self.cancel_result
