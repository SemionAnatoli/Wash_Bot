from datetime import date

from app.bot.customer_booking.handlers import (
    handle_addon_selected,
    handle_addons_done,
    handle_booking_start,
    handle_date_selected,
    handle_main_service_selected,
    handle_start,
    router,
)
from app.bot.customer_booking.messages import NO_SERVICES_TEXT
from app.bot.customer_booking.states import CustomerBookingFlow
from app.services.customer_booking import ServiceMenu
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
    service = FakeCustomerBookingService()

    await handle_booking_start(
        callback,
        state,
        customer_booking_service=service,
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert service.requested_menus == [{"car_wash_id": 10}]
    assert state.data["car_wash_id"] == 10
    assert state.data["branch_id"] == 20
    assert "service_menu" not in state.data
    assert state.state == CustomerBookingFlow.choosing_main_service
    assert "Выберите услугу" in first_text(callback.message)


async def test_booking_start_without_services_does_not_enter_service_state() -> None:
    callback = FakeCallbackQuery(data="book:start")
    state = FakeState()
    service = FakeCustomerBookingService(menu=ServiceMenu(main_services=[], addons=[]))

    await handle_booking_start(
        callback,
        state,
        customer_booking_service=service,
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert state.state is None
    assert first_text(callback.message) == NO_SERVICES_TEXT


async def test_main_service_selection_stores_service_and_shows_addons() -> None:
    callback = FakeCallbackQuery(data="book:main:1")
    state = FakeState(data={"car_wash_id": 10})
    service = FakeCustomerBookingService()

    await handle_main_service_selected(callback, state, customer_booking_service=service)

    assert service.requested_menus == [{"car_wash_id": 10}]
    assert state.data["main_service_id"] == 1
    assert state.data["addon_service_ids"] == []
    assert "service_menu" not in state.data
    assert state.state == CustomerBookingFlow.choosing_addons
    assert "дополнительные" in first_text(callback.message).lower()


async def test_addon_selection_toggles_selected_id() -> None:
    callback = FakeCallbackQuery(data="book:addon:2")
    state = FakeState(
        data={
            "car_wash_id": 10,
            "addon_service_ids": [],
        }
    )
    service = FakeCustomerBookingService()

    await handle_addon_selected(callback, state, customer_booking_service=service)
    await handle_addon_selected(callback, state, customer_booking_service=service)

    assert service.requested_menus == [{"car_wash_id": 10}, {"car_wash_id": 10}]
    assert state.data["addon_service_ids"] == []
    assert "service_menu" not in state.data


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
    assert state.data["selected_date"] == "2026-05-18"
    assert "available_slots" not in state.data
    assert state.state == CustomerBookingFlow.choosing_slot
    assert "Выберите свободное время" in first_text(callback.message)


async def test_date_selection_without_slots_keeps_date_selection_and_offers_dates() -> None:
    callback = FakeCallbackQuery(data="book:date:2026-05-18")
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "main_service_id": 1,
            "addon_service_ids": [2],
        }
    )
    service = FakeCustomerBookingService(slots=[])

    await handle_date_selected(callback, state, customer_booking_service=service)

    assert state.state == CustomerBookingFlow.choosing_date
    assert state.data["selected_date"] == "2026-05-18"
    assert "available_slots" not in state.data
    reply_markup = callback.message.answers[0]["reply_markup"]
    assert reply_markup is not None
    callback_data = reply_markup.inline_keyboard[0][0].callback_data
    assert callback_data is not None
    assert callback_data.startswith("book:date:")


def test_booking_callback_handlers_are_state_scoped() -> None:
    callback_handlers = router.callback_query.handlers

    assert callback_handlers[1].filters[0].callback.states == (
        CustomerBookingFlow.choosing_main_service,
    )
    assert callback_handlers[2].filters[0].callback.states == (CustomerBookingFlow.choosing_addons,)
    assert callback_handlers[3].filters[0].callback.states == (CustomerBookingFlow.choosing_addons,)
    assert callback_handlers[4].filters[0].callback.states == (CustomerBookingFlow.choosing_date,)
