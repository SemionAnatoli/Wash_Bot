from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.customer_booking import (
    ActiveCustomerBooking,
    ServiceMenu,
    ServiceOption,
)


@dataclass
class FakeTelegramUser:
    id: int = 1001
    username: str | None = "ivan"


@dataclass
class FakeMessage:
    text: str | None = None
    from_user: FakeTelegramUser | None = field(default_factory=FakeTelegramUser)
    answers: list[dict[str, Any]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage = field(default_factory=FakeMessage)
    from_user: FakeTelegramUser | None = field(default_factory=FakeTelegramUser)
    answered: bool = False

    async def answer(self) -> None:
        self.answered = True


@dataclass
class FakeState:
    data: dict[str, Any] = field(default_factory=dict)
    state: Any = None
    cleared: bool = False

    async def set_state(self, state: Any) -> None:
        self.state = state

    async def update_data(self, **kwargs: Any) -> None:
        self.data.update(kwargs)

    async def set_data(self, data: dict[str, Any]) -> None:
        self.data = data

    async def get_data(self) -> dict[str, Any]:
        return dict(self.data)

    async def clear(self) -> None:
        self.data.clear()
        self.state = None
        self.cleared = True


def option(service_id: int, title: str, *, is_addon: bool = False) -> ServiceOption:
    return ServiceOption(
        id=service_id,
        title=title,
        category="addon" if is_addon else "wash",
        price=Decimal("100"),
        duration_minutes=30,
        is_addon=is_addon,
    )


@dataclass
class FakeCustomerBookingService:
    menu: ServiceMenu = field(
        default_factory=lambda: ServiceMenu(
            main_services=[option(1, "Стандарт")],
            addons=[option(2, "Воск", is_addon=True)],
        )
    )
    slots: list[datetime] = field(default_factory=lambda: [datetime(2026, 5, 18, 10)])
    active_booking: ActiveCustomerBooking | None = field(
        default_factory=lambda: ActiveCustomerBooking(
            booking_id=42,
            status="confirmed",
            start_at=datetime(2026, 5, 18, 10),
            end_at=datetime(2026, 5, 18, 11),
            customer_name="Иван",
            customer_phone="+79131234567",
            vehicle_plate="A123BC154",
            services=[
                option(1, "Стандарт"),
                option(2, "Воск", is_addon=True),
            ],
        )
    )
    requested_menus: list[dict[str, Any]] = field(default_factory=list)
    requested_slots: list[dict[str, Any]] = field(default_factory=list)
    requested_active_bookings: list[dict[str, Any]] = field(default_factory=list)
    cancel_requests: list[dict[str, Any]] = field(default_factory=list)
    created_bookings: list[dict[str, Any]] = field(default_factory=list)
    booking_status: str = "confirmed"
    cancel_result: bool = True
    slots_error: Exception | None = None
    create_error: Exception | None = None
    cancel_error: Exception | None = None

    async def get_service_menu(self, *, car_wash_id: int) -> ServiceMenu:
        self.requested_menus.append({"car_wash_id": car_wash_id})
        return self.menu

    async def get_available_slots(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        selected_service_ids: list[int],
        day: date,
    ) -> list[datetime]:
        self.requested_slots.append(
            {
                "car_wash_id": car_wash_id,
                "branch_id": branch_id,
                "selected_service_ids": selected_service_ids,
                "day": day,
            }
        )
        if self.slots_error is not None:
            raise self.slots_error
        return self.slots

    async def create_booking(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        selected_service_ids: list[int],
        start_at: datetime,
        customer_name: str,
        customer_phone: str,
        vehicle_plate: str,
        telegram_user_id: int | None = None,
        telegram_username: str | None = None,
    ) -> Any:
        if self.create_error is not None:
            raise self.create_error

        self.created_bookings.append(
            {
                "car_wash_id": car_wash_id,
                "branch_id": branch_id,
                "selected_service_ids": selected_service_ids,
                "start_at": start_at,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "vehicle_plate": vehicle_plate,
                "telegram_user_id": telegram_user_id,
                "telegram_username": telegram_username,
            }
        )
        return type("BookingResult", (), {"id": 42, "status": self.booking_status})()

    async def get_active_booking(
        self,
        *,
        car_wash_id: int,
        telegram_user_id: int,
        now: datetime | None = None,
    ) -> ActiveCustomerBooking | None:
        self.requested_active_bookings.append(
            {
                "car_wash_id": car_wash_id,
                "telegram_user_id": telegram_user_id,
                "now": now,
            }
        )
        return self.active_booking

    async def cancel_active_booking(
        self,
        *,
        car_wash_id: int,
        telegram_user_id: int,
        now: datetime | None = None,
        cancellation_deadline_minutes: int = 60,
    ) -> bool:
        self.cancel_requests.append(
            {
                "car_wash_id": car_wash_id,
                "telegram_user_id": telegram_user_id,
                "now": now,
                "cancellation_deadline_minutes": cancellation_deadline_minutes,
            }
        )
        if self.cancel_error is not None:
            raise self.cancel_error
        return self.cancel_result


@dataclass
class FakeAdminBookingNotifier:
    sent_booking_ids: list[int] = field(default_factory=list)
    send_error: Exception | None = None

    async def notify_new_booking(self, *, car_wash_id: int, booking_id: int) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent_booking_ids.append(booking_id)
