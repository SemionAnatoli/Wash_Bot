from datetime import date, timedelta
from typing import Any, cast

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    parse_date_callback,
    parse_id_callback,
)
from app.bot.customer_booking.keyboards import (
    addons_keyboard,
    booking_entry_keyboard,
    date_keyboard,
    main_services_keyboard,
    slots_keyboard,
)
from app.bot.customer_booking.messages import (
    CHOOSE_ADDONS_TEXT,
    CHOOSE_DATE_TEXT,
    CHOOSE_SERVICE_TEXT,
    CHOOSE_SLOT_TEXT,
    NO_SERVICES_TEXT,
    NO_SLOTS_TEXT,
    START_TEXT,
)
from app.bot.customer_booking.states import CustomerBookingFlow
from app.services.customer_booking import CustomerBookingService, ServiceMenu

router = Router(name="customer_booking")


def _callback_message(callback: CallbackQuery) -> Message:
    if callback.message is None:
        raise RuntimeError("Callback query has no message.")
    return cast(Message, callback.message)


def _next_dates(start: date | None = None) -> list[date]:
    first_day = start or date.today()
    return [first_day + timedelta(days=offset) for offset in range(7)]


def _selected_service_ids(data: dict[str, Any]) -> list[int]:
    return [
        int(data["main_service_id"]),
        *[int(service_id) for service_id in data["addon_service_ids"]],
    ]


async def handle_start(message: Message) -> None:
    await message.answer(START_TEXT, reply_markup=booking_entry_keyboard())


async def handle_booking_start(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
    default_car_wash_id: int,
    default_branch_id: int,
) -> None:
    await callback.answer()

    service_menu = await customer_booking_service.get_service_menu(car_wash_id=default_car_wash_id)
    await state.update_data(
        car_wash_id=default_car_wash_id,
        branch_id=default_branch_id,
        service_menu=service_menu,
    )
    await state.set_state(CustomerBookingFlow.choosing_main_service)

    if not service_menu.main_services:
        await _callback_message(callback).answer(NO_SERVICES_TEXT)
        return

    await _callback_message(callback).answer(
        CHOOSE_SERVICE_TEXT,
        reply_markup=main_services_keyboard(service_menu.main_services),
    )


async def handle_main_service_selected(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    main_service_id = parse_id_callback(cast(str, callback.data), prefix="book:main")
    data = await state.get_data()
    service_menu = cast(ServiceMenu, data["service_menu"])
    await state.update_data(main_service_id=main_service_id, addon_service_ids=[])
    await state.set_state(CustomerBookingFlow.choosing_addons)

    await _callback_message(callback).answer(
        CHOOSE_ADDONS_TEXT,
        reply_markup=addons_keyboard(service_menu.addons, selected_ids=set()),
    )


async def handle_addon_selected(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    addon_service_id = parse_id_callback(cast(str, callback.data), prefix="book:addon")
    data = await state.get_data()
    service_menu = cast(ServiceMenu, data["service_menu"])
    selected_ids = {int(service_id) for service_id in data.get("addon_service_ids", [])}
    if addon_service_id in selected_ids:
        selected_ids.remove(addon_service_id)
    else:
        selected_ids.add(addon_service_id)

    await state.update_data(addon_service_ids=sorted(selected_ids))
    await _callback_message(callback).answer(
        CHOOSE_ADDONS_TEXT,
        reply_markup=addons_keyboard(service_menu.addons, selected_ids=selected_ids),
    )


async def handle_addons_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    await state.set_state(CustomerBookingFlow.choosing_date)
    await _callback_message(callback).answer(
        CHOOSE_DATE_TEXT,
        reply_markup=date_keyboard(_next_dates()),
    )


async def handle_date_selected(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
) -> None:
    await callback.answer()

    selected_day = date.fromisoformat(parse_date_callback(cast(str, callback.data)))
    data = await state.get_data()
    selected_service_ids = _selected_service_ids(data)
    slots = await customer_booking_service.get_available_slots(
        car_wash_id=int(data["car_wash_id"]),
        branch_id=int(data["branch_id"]),
        selected_service_ids=selected_service_ids,
        day=selected_day,
    )
    await state.update_data(selected_date=selected_day, available_slots=slots)
    await state.set_state(CustomerBookingFlow.choosing_slot)

    if not slots:
        await _callback_message(callback).answer(NO_SLOTS_TEXT)
        return

    await _callback_message(callback).answer(
        CHOOSE_SLOT_TEXT,
        reply_markup=slots_keyboard(slots),
    )


router.message.register(handle_start, CommandStart())
router.callback_query.register(handle_booking_start, F.data == BOOKING_START_CALLBACK)
router.callback_query.register(handle_main_service_selected, F.data.startswith("book:main:"))
router.callback_query.register(handle_addon_selected, F.data.startswith("book:addon:"))
router.callback_query.register(handle_addons_done, F.data == ADDONS_DONE_CALLBACK)
router.callback_query.register(handle_date_selected, F.data.startswith("book:date:"))
