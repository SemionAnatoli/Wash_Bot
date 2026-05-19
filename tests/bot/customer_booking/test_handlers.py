from datetime import date

from app.bot.customer_booking.handlers import (
    handle_addon_selected,
    handle_addons_done,
    handle_booking_start,
    handle_date_selected,
    handle_main_service_selected,
    handle_start,
)
from app.bot.customer_booking.states import CustomerBookingFlow
from tests.bot.customer_booking.fakes import (
    FakeCallbackQuery,
    FakeCustomerBookingService,
    FakeMessage,
    FakeState,
)


def first_text(message: FakeMessage) -> str:
    return message.answers[0]["text"]


async def test_start_shows_booking_entry_keyboard() -> None:
    message = FakeMessage()

    await handle_start(message)

    assert "записаться" in first_text(message).lower()
    assert message.answers[0]["reply_markup"].inline_keyboard[0][0].callback_data == "book:start"


async def test_booking_start_loads_menu_and_sets_context() -> None:
    callback = FakeCallbackQuery(data="book:start")
    state = FakeState()

    await handle_booking_start(
        callback,
        state,
        customer_booking_service=FakeCustomerBookingService(),
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert state.data["car_wash_id"] == 10
    assert state.data["branch_id"] == 20
    assert state.data["service_menu"].main_services[0].id == 1
    assert state.state == CustomerBookingFlow.choosing_main_service
    assert "Выберите услугу" in first_text(callback.message)


async def test_main_service_selection_stores_service_and_shows_addons() -> None:
    callback = FakeCallbackQuery(data="book:main:1")
    state = FakeState(data={"service_menu": FakeCustomerBookingService().menu})

    await handle_main_service_selected(callback, state)

    assert state.data["main_service_id"] == 1
    assert state.data["addon_service_ids"] == []
    assert state.state == CustomerBookingFlow.choosing_addons
    assert "дополнительные" in first_text(callback.message).lower()


async def test_addon_selection_toggles_selected_id() -> None:
    callback = FakeCallbackQuery(data="book:addon:2")
    state = FakeState(
        data={
            "service_menu": FakeCustomerBookingService().menu,
            "addon_service_ids": [],
        }
    )

    await handle_addon_selected(callback, state)
    await handle_addon_selected(callback, state)

    assert state.data["addon_service_ids"] == []


async def test_addons_done_shows_date_choices() -> None:
    callback = FakeCallbackQuery(data="book:addons_done")
    state = FakeState()

    await handle_addons_done(callback, state)

    assert state.state == CustomerBookingFlow.choosing_date
    assert "Выберите дату" in first_text(callback.message)


async def test_date_selection_requests_slots_for_selected_services() -> None:
    callback = FakeCallbackQuery(data="book:date:2026-05-18")
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "main_service_id": 1,
            "addon_service_ids": [2],
        }
    )
    service = FakeCustomerBookingService()

    await handle_date_selected(callback, state, customer_booking_service=service)

    assert service.requested_slots[0]["selected_service_ids"] == [1, 2]
    assert service.requested_slots[0]["day"] == date(2026, 5, 18)
    assert state.state == CustomerBookingFlow.choosing_slot
    assert "Выберите свободное время" in first_text(callback.message)
