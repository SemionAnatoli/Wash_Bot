from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.customer_booking import ServiceMenu, ServiceOption


@dataclass
class FakeMessage:
    text: str | None = None
    answers: list[dict[str, Any]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage = field(default_factory=FakeMessage)
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
    requested_slots: list[dict[str, Any]] = field(default_factory=list)

    async def get_service_menu(self, *, car_wash_id: int) -> ServiceMenu:
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
        return self.slots
