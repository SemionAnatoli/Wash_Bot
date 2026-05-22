from datetime import date, datetime

import pytest

from app.bot.customer_booking.callbacks import CANCEL_FLOW_CALLBACK, CHANGE_SERVICES_CALLBACK
from app.bot.customer_booking.handlers import (
    handle_addon_selected,
    handle_addons_done,
    handle_booking_confirmed,
    handle_booking_start,
    handle_cancel_flow,
    handle_change_services,
    handle_change_time,
    handle_date_selected,
    handle_main_service_selected,
    handle_name_received,
    handle_phone_received,
    handle_slot_selected,
    handle_start,
    handle_vehicle_plate_received,
    router,
)
from app.bot.customer_booking.messages import (
    NO_SERVICES_TEXT,
    SELECTED_SERVICES_UNAVAILABLE_TEXT,
    SLOT_STALE_TEXT,
)
from app.bot.customer_booking.states import CustomerBookingFlow
from app.domain.errors import BookingSlotUnavailableError, DomainError
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


async def test_booking_start_without_services_clears_existing_flow_state() -> None:
    callback = FakeCallbackQuery(data="book:start")
    state = FakeState(data={"main_service_id": 1}, state=CustomerBookingFlow.choosing_date)
    service = FakeCustomerBookingService(menu=ServiceMenu(main_services=[], addons=[]))

    await handle_booking_start(
        callback,
        state,
        customer_booking_service=service,
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert state.cleared is True
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
    callbacks = [button.callback_data for row in reply_markup.inline_keyboard for button in row]
    assert CHANGE_SERVICES_CALLBACK in callbacks
    assert CANCEL_FLOW_CALLBACK in callbacks


async def test_date_selection_with_invalid_services_clears_state_and_shows_recovery() -> None:
    callback = FakeCallbackQuery(data="book:date:2026-05-18")
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "main_service_id": 999,
            "addon_service_ids": [],
        },
        state=CustomerBookingFlow.choosing_date,
    )
    service = FakeCustomerBookingService(
        slots_error=DomainError("One or more services were not found.")
    )

    await handle_date_selected(callback, state, customer_booking_service=service)

    assert state.cleared is True
    assert state.data == {}
    assert first_text(callback.message) == SELECTED_SERVICES_UNAVAILABLE_TEXT


async def test_slot_selection_stores_start_and_asks_for_name() -> None:
    callback = FakeCallbackQuery(data="book:slot:2026-05-18T10:00")
    state = FakeState()

    await handle_slot_selected(callback, state)

    assert state.data["start_at"] == "2026-05-18T10:00:00"
    assert state.state == CustomerBookingFlow.waiting_for_name
    assert "имя" in first_text(callback.message).lower()


async def test_invalid_phone_keeps_phone_state() -> None:
    message = FakeMessage(text="123")
    state = FakeState()

    await handle_phone_received(message, state)

    assert state.state == CustomerBookingFlow.waiting_for_phone
    assert "номер телефона" in first_text(message).lower()


async def test_customer_input_reaches_confirmation_summary() -> None:
    service = FakeCustomerBookingService()
    state = FakeState(
        data={
            "car_wash_id": 10,
            "main_service_id": 1,
            "addon_service_ids": [2],
            "start_at": "2026-05-18T10:00:00",
        }
    )

    await handle_name_received(FakeMessage(text=" Иван "), state)
    await handle_phone_received(FakeMessage(text="8 (913) 123-45-67"), state)
    plate_message = FakeMessage(text="a123bc154")
    await handle_vehicle_plate_received(
        plate_message,
        state,
        customer_booking_service=service,
    )

    assert service.requested_menus[-1] == {"car_wash_id": 10}
    assert state.data["customer_name"] == "Иван"
    assert state.data["customer_phone"] == "+79131234567"
    assert state.data["vehicle_plate"] == "A123BC154"
    assert "service_menu" not in state.data
    assert state.state == CustomerBookingFlow.confirming
    assert "Проверьте" in first_text(plate_message)


async def test_unavailable_selected_service_clears_state_and_shows_recovery_message() -> None:
    service = FakeCustomerBookingService()
    state = FakeState(
        data={
            "car_wash_id": 10,
            "main_service_id": 999,
            "addon_service_ids": [],
            "start_at": "2026-05-18T10:00:00",
            "customer_name": "Иван",
            "customer_phone": "+79131234567",
        }
    )
    plate_message = FakeMessage(text="a123bc154")

    await handle_vehicle_plate_received(
        plate_message,
        state,
        customer_booking_service=service,
    )

    assert state.cleared is True
    assert state.data == {}
    assert first_text(plate_message) == SELECTED_SERVICES_UNAVAILABLE_TEXT
    assert "Проверьте" not in first_text(plate_message)
    assert len(plate_message.answers) == 1


async def test_booking_confirmation_creates_booking_and_clears_state() -> None:
    service = FakeCustomerBookingService()
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "main_service_id": 1,
            "addon_service_ids": [2],
            "start_at": "2026-05-18T10:00:00",
            "customer_name": "Иван",
            "customer_phone": "+79131234567",
            "vehicle_plate": "A123BC154",
        }
    )
    callback = FakeCallbackQuery(data="book:confirm")

    await handle_booking_confirmed(callback, state, customer_booking_service=service)

    assert service.created_bookings[0] == {
        "car_wash_id": 10,
        "branch_id": 20,
        "selected_service_ids": [1, 2],
        "start_at": datetime(2026, 5, 18, 10),
        "customer_name": "Иван",
        "customer_phone": "+79131234567",
        "vehicle_plate": "A123BC154",
    }
    assert "подтверждена" in first_text(callback.message).lower()
    assert state.cleared is True


async def test_booking_confirmation_handles_stale_slot() -> None:
    service = FakeCustomerBookingService(
        create_error=BookingSlotUnavailableError("Capacity is full.")
    )
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "main_service_id": 1,
            "addon_service_ids": [],
            "start_at": "2026-05-18T10:00:00",
            "customer_name": "Иван",
            "customer_phone": "+79131234567",
            "vehicle_plate": "A123BC154",
        }
    )
    callback = FakeCallbackQuery(data="book:confirm")

    await handle_booking_confirmed(callback, state, customer_booking_service=service)

    assert first_text(callback.message) == SLOT_STALE_TEXT
    assert callback.message.answers[0]["reply_markup"].inline_keyboard[0][0].callback_data == (
        "book:confirm"
    )
    assert state.state == CustomerBookingFlow.confirming
    assert state.cleared is False
    assert service.created_bookings == []


async def test_booking_confirmation_propagates_unexpected_domain_error() -> None:
    service = FakeCustomerBookingService(create_error=DomainError("Branch was not found."))
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "main_service_id": 1,
            "addon_service_ids": [],
            "start_at": "2026-05-18T10:00:00",
            "customer_name": "РРІР°РЅ",
            "customer_phone": "+79131234567",
            "vehicle_plate": "A123BC154",
        }
    )
    callback = FakeCallbackQuery(data="book:confirm")

    with pytest.raises(DomainError, match="Branch was not found."):
        await handle_booking_confirmed(callback, state, customer_booking_service=service)

    assert callback.message.answers == []
    assert service.created_bookings == []


async def test_change_time_returns_to_date_selection() -> None:
    callback = FakeCallbackQuery(data="book:change_time")
    state = FakeState()

    await handle_change_time(callback, state)

    assert state.state == CustomerBookingFlow.choosing_date
    assert "Выберите дату" in first_text(callback.message)


async def test_change_services_returns_to_menu() -> None:
    callback = FakeCallbackQuery(data="book:change_services")
    state = FakeState(data={"car_wash_id": 10, "main_service_id": 1, "addon_service_ids": [2]})
    service = FakeCustomerBookingService()

    await handle_change_services(callback, state, customer_booking_service=service)

    assert service.requested_menus[-1] == {"car_wash_id": 10}
    assert state.state == CustomerBookingFlow.choosing_main_service
    assert state.data["car_wash_id"] == 10
    assert "main_service_id" not in state.data
    assert "addon_service_ids" not in state.data
    assert "Выберите услугу" in first_text(callback.message)


async def test_cancel_flow_clears_state() -> None:
    callback = FakeCallbackQuery(data="book:cancel_flow")
    state = FakeState(data={"main_service_id": 1})

    await handle_cancel_flow(callback, state)

    assert state.cleared is True
    assert "отменена" in first_text(callback.message).lower()


def test_booking_callback_handlers_are_state_scoped() -> None:
    callback_handlers = router.callback_query.handlers

    assert callback_handlers[1].filters[0].callback.states == (
        CustomerBookingFlow.choosing_main_service,
    )
    assert callback_handlers[2].filters[0].callback.states == (CustomerBookingFlow.choosing_addons,)
    assert callback_handlers[3].filters[0].callback.states == (CustomerBookingFlow.choosing_addons,)
    assert callback_handlers[4].filters[0].callback.states == (CustomerBookingFlow.choosing_date,)
    assert callback_handlers[5].filters[0].callback.states == (CustomerBookingFlow.choosing_slot,)
    assert callback_handlers[6].filters[0].callback.states == (CustomerBookingFlow.confirming,)
    assert callback_handlers[7].filters[0].callback.states == (CustomerBookingFlow.confirming,)
    assert callback_handlers[8].filters[0].callback.states == (
        CustomerBookingFlow.confirming,
        CustomerBookingFlow.choosing_date,
    )
    assert callback_handlers[9].filters[0].callback.states == (
        CustomerBookingFlow.choosing_main_service,
        CustomerBookingFlow.choosing_addons,
        CustomerBookingFlow.choosing_date,
        CustomerBookingFlow.choosing_slot,
        CustomerBookingFlow.waiting_for_name,
        CustomerBookingFlow.waiting_for_phone,
        CustomerBookingFlow.waiting_for_vehicle_plate,
        CustomerBookingFlow.confirming,
    )


def test_booking_message_handlers_are_state_scoped() -> None:
    message_handlers = router.message.handlers

    assert message_handlers[1].filters[0].callback.states == (CustomerBookingFlow.waiting_for_name,)
    assert message_handlers[2].filters[0].callback.states == (
        CustomerBookingFlow.waiting_for_phone,
    )
    assert message_handlers[3].filters[0].callback.states == (
        CustomerBookingFlow.waiting_for_vehicle_plate,
    )
