from datetime import date, datetime, timedelta
from typing import Any, cast

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CANCEL_ACTIVE_BOOKING_CALLBACK,
    CANCEL_FLOW_CALLBACK,
    CHANGE_SERVICES_CALLBACK,
    CHANGE_TIME_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
    MY_ACTIVE_BOOKING_CALLBACK,
    parse_date_callback,
    parse_id_callback,
    parse_slot_callback,
)
from app.bot.customer_booking.keyboards import (
    active_booking_keyboard,
    addons_keyboard,
    booking_entry_keyboard,
    confirmation_keyboard,
    date_keyboard,
    main_services_keyboard,
    no_slots_keyboard,
    slots_keyboard,
)
from app.bot.customer_booking.messages import (
    ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT,
    ACTIVE_BOOKING_CANCELLED_TEXT,
    ACTIVE_BOOKING_EMPTY_TEXT,
    ASK_NAME_TEXT,
    ASK_PHONE_TEXT,
    ASK_VEHICLE_PLATE_TEXT,
    CHOOSE_ADDONS_TEXT,
    CHOOSE_DATE_TEXT,
    CHOOSE_SERVICE_TEXT,
    CHOOSE_SLOT_TEXT,
    CONFIRMED_TEXT,
    INVALID_PHONE_TEXT,
    INVALID_PLATE_TEXT,
    NO_SERVICES_TEXT,
    NO_SLOTS_TEXT,
    PENDING_TEXT,
    SELECTED_SERVICES_UNAVAILABLE_TEXT,
    SLOT_STALE_TEXT,
    START_TEXT,
    format_active_booking_summary,
    format_booking_summary,
)
from app.bot.customer_booking.states import CustomerBookingFlow
from app.domain.errors import (
    BookingSlotUnavailableError,
    CancellationTooLateError,
    DomainError,
    ValidationError,
)
from app.domain.validation import normalize_name, normalize_phone, normalize_vehicle_plate
from app.services.customer_booking import CustomerBookingService, ServiceMenu, ServiceOption

router = Router(name="customer_booking")
_ALLOWED_STATE_KEYS = (
    "car_wash_id",
    "branch_id",
    "main_service_id",
    "addon_service_ids",
    "selected_date",
    "start_at",
    "customer_name",
    "customer_phone",
    "vehicle_plate",
)


def _callback_message(callback: CallbackQuery) -> Message:
    if callback.message is None:
        raise RuntimeError("Callback query has no message.")
    return cast(Message, callback.message)


def _telegram_user(callback_or_message: CallbackQuery | Message) -> tuple[int, str | None]:
    user = callback_or_message.from_user
    if user is None:
        raise RuntimeError("Telegram user is missing.")
    return user.id, user.username


def _next_dates(start: date | None = None) -> list[date]:
    first_day = start or date.today()
    return [first_day + timedelta(days=offset) for offset in range(7)]


def _selected_service_ids(data: dict[str, Any]) -> list[int]:
    return [
        int(data["main_service_id"]),
        *[int(service_id) for service_id in data["addon_service_ids"]],
    ]


def _find_service(menu: ServiceMenu, service_id: int) -> ServiceOption:
    for service in [*menu.main_services, *menu.addons]:
        if service.id == service_id:
            return service
    raise ValueError("Selected service is missing from service menu.")


def _selected_options(
    data: dict[str, Any],
    menu: ServiceMenu,
) -> tuple[ServiceOption, list[ServiceOption]]:
    main_service = _find_service(menu, int(data["main_service_id"]))
    addons = [
        _find_service(menu, int(service_id)) for service_id in data.get("addon_service_ids", [])
    ]
    return main_service, addons


async def _update_allowed_data(state: FSMContext, **updates: Any) -> None:
    data = await state.get_data()
    data.update(updates)
    await state.set_data({key: data[key] for key in _ALLOWED_STATE_KEYS if key in data})


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
    await state.set_data(
        {
            "car_wash_id": default_car_wash_id,
            "branch_id": default_branch_id,
        }
    )

    if not service_menu.main_services:
        await state.clear()
        await _callback_message(callback).answer(NO_SERVICES_TEXT)
        return

    await state.set_state(CustomerBookingFlow.choosing_main_service)
    await _callback_message(callback).answer(
        CHOOSE_SERVICE_TEXT,
        reply_markup=main_services_keyboard(service_menu.main_services),
    )


async def handle_main_service_selected(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
) -> None:
    await callback.answer()

    main_service_id = parse_id_callback(cast(str, callback.data), prefix="book:main")
    data = await state.get_data()
    service_menu = await customer_booking_service.get_service_menu(
        car_wash_id=int(data["car_wash_id"])
    )
    await _update_allowed_data(state, main_service_id=main_service_id, addon_service_ids=[])
    await state.set_state(CustomerBookingFlow.choosing_addons)

    await _callback_message(callback).answer(
        CHOOSE_ADDONS_TEXT,
        reply_markup=addons_keyboard(service_menu.addons, selected_ids=set()),
    )


async def handle_addon_selected(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
) -> None:
    await callback.answer()

    addon_service_id = parse_id_callback(cast(str, callback.data), prefix="book:addon")
    data = await state.get_data()
    service_menu = await customer_booking_service.get_service_menu(
        car_wash_id=int(data["car_wash_id"])
    )
    selected_ids = {int(service_id) for service_id in data.get("addon_service_ids", [])}
    if addon_service_id in selected_ids:
        selected_ids.remove(addon_service_id)
    else:
        selected_ids.add(addon_service_id)

    await _update_allowed_data(state, addon_service_ids=sorted(selected_ids))
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
    try:
        slots = await customer_booking_service.get_available_slots(
            car_wash_id=int(data["car_wash_id"]),
            branch_id=int(data["branch_id"]),
            selected_service_ids=selected_service_ids,
            day=selected_day,
        )
    except DomainError:
        await state.clear()
        await _callback_message(callback).answer(SELECTED_SERVICES_UNAVAILABLE_TEXT)
        return
    await _update_allowed_data(state, selected_date=selected_day.isoformat())

    if not slots:
        await state.set_state(CustomerBookingFlow.choosing_date)
        await _callback_message(callback).answer(
            NO_SLOTS_TEXT,
            reply_markup=no_slots_keyboard(_next_dates(selected_day)),
        )
        return

    await state.set_state(CustomerBookingFlow.choosing_slot)
    await _callback_message(callback).answer(
        CHOOSE_SLOT_TEXT,
        reply_markup=slots_keyboard(slots),
    )


async def handle_slot_selected(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    start_at = parse_slot_callback(cast(str, callback.data))
    await _update_allowed_data(state, start_at=start_at.isoformat())
    await state.set_state(CustomerBookingFlow.waiting_for_name)
    await _callback_message(callback).answer(ASK_NAME_TEXT)


async def handle_name_received(message: Message, state: FSMContext) -> None:
    try:
        name = normalize_name(message.text or "")
    except ValidationError:
        await state.set_state(CustomerBookingFlow.waiting_for_name)
        await message.answer(ASK_NAME_TEXT)
        return

    await _update_allowed_data(state, customer_name=name)
    await state.set_state(CustomerBookingFlow.waiting_for_phone)
    await message.answer(ASK_PHONE_TEXT)


async def handle_phone_received(message: Message, state: FSMContext) -> None:
    try:
        phone = normalize_phone(message.text or "")
    except ValidationError:
        await state.set_state(CustomerBookingFlow.waiting_for_phone)
        await message.answer(INVALID_PHONE_TEXT)
        return

    await _update_allowed_data(state, customer_phone=phone)
    await state.set_state(CustomerBookingFlow.waiting_for_vehicle_plate)
    await message.answer(ASK_VEHICLE_PLATE_TEXT)


async def handle_vehicle_plate_received(
    message: Message,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
) -> None:
    try:
        vehicle_plate = normalize_vehicle_plate(message.text or "")
    except ValidationError:
        await state.set_state(CustomerBookingFlow.waiting_for_vehicle_plate)
        await message.answer(INVALID_PLATE_TEXT)
        return

    await _update_allowed_data(state, vehicle_plate=vehicle_plate)
    data = await state.get_data()
    menu = await customer_booking_service.get_service_menu(car_wash_id=int(data["car_wash_id"]))
    try:
        main_service, addons = _selected_options(data, menu)
    except ValueError:
        await state.clear()
        await message.answer(SELECTED_SERVICES_UNAVAILABLE_TEXT)
        return

    await state.set_state(CustomerBookingFlow.confirming)
    await message.answer(
        format_booking_summary(
            main_service=main_service,
            addons=addons,
            start_at=datetime.fromisoformat(data["start_at"]),
            customer_name=data["customer_name"],
            customer_phone=data["customer_phone"],
            vehicle_plate=vehicle_plate,
        ),
        reply_markup=confirmation_keyboard(),
    )


async def handle_booking_confirmed(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
) -> None:
    await callback.answer()

    data = await state.get_data()
    telegram_user_id, telegram_username = _telegram_user(callback)
    try:
        booking = await customer_booking_service.create_booking(
            car_wash_id=int(data["car_wash_id"]),
            branch_id=int(data["branch_id"]),
            selected_service_ids=_selected_service_ids(data),
            start_at=datetime.fromisoformat(data["start_at"]),
            customer_name=str(data["customer_name"]),
            customer_phone=str(data["customer_phone"]),
            vehicle_plate=str(data["vehicle_plate"]),
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
        )
    except BookingSlotUnavailableError:
        await state.set_state(CustomerBookingFlow.confirming)
        await _callback_message(callback).answer(
            SLOT_STALE_TEXT,
            reply_markup=confirmation_keyboard(),
        )
        return

    await state.clear()
    text = CONFIRMED_TEXT if booking.status == "confirmed" else PENDING_TEXT
    await _callback_message(callback).answer(text)


async def handle_active_booking_requested(
    callback: CallbackQuery,
    *,
    customer_booking_service: CustomerBookingService,
    default_car_wash_id: int,
) -> None:
    await callback.answer()
    telegram_user_id, _ = _telegram_user(callback)
    booking = await customer_booking_service.get_active_booking(
        car_wash_id=default_car_wash_id,
        telegram_user_id=telegram_user_id,
    )
    if booking is None:
        await _callback_message(callback).answer(ACTIVE_BOOKING_EMPTY_TEXT)
        return

    await _callback_message(callback).answer(
        format_active_booking_summary(booking),
        reply_markup=active_booking_keyboard(),
    )


async def handle_active_booking_cancelled(
    callback: CallbackQuery,
    *,
    customer_booking_service: CustomerBookingService,
    default_car_wash_id: int,
) -> None:
    await callback.answer()
    telegram_user_id, _ = _telegram_user(callback)
    try:
        cancelled = await customer_booking_service.cancel_active_booking(
            car_wash_id=default_car_wash_id,
            telegram_user_id=telegram_user_id,
            cancellation_deadline_minutes=60,
        )
    except CancellationTooLateError:
        await _callback_message(callback).answer(ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT)
        return

    text = ACTIVE_BOOKING_CANCELLED_TEXT if cancelled else ACTIVE_BOOKING_EMPTY_TEXT
    await _callback_message(callback).answer(text)


async def handle_change_time(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(CustomerBookingFlow.choosing_date)
    await _callback_message(callback).answer(
        CHOOSE_DATE_TEXT,
        reply_markup=date_keyboard(_next_dates()),
    )


async def handle_change_services(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
) -> None:
    await callback.answer()
    data = await state.get_data()
    car_wash_id = int(data["car_wash_id"])
    service_menu = await customer_booking_service.get_service_menu(car_wash_id=car_wash_id)
    next_data = {"car_wash_id": car_wash_id}
    if "branch_id" in data:
        next_data["branch_id"] = int(data["branch_id"])
    await state.set_data(next_data)
    await state.set_state(CustomerBookingFlow.choosing_main_service)
    await _callback_message(callback).answer(
        CHOOSE_SERVICE_TEXT,
        reply_markup=main_services_keyboard(service_menu.main_services),
    )


async def handle_cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await _callback_message(callback).answer("Запись отменена.")


router.message.register(handle_start, CommandStart())
router.callback_query.register(handle_booking_start, F.data == BOOKING_START_CALLBACK)
router.callback_query.register(
    handle_active_booking_requested,
    F.data == MY_ACTIVE_BOOKING_CALLBACK,
)
router.callback_query.register(
    handle_active_booking_cancelled,
    F.data == CANCEL_ACTIVE_BOOKING_CALLBACK,
)
router.callback_query.register(
    handle_main_service_selected,
    StateFilter(CustomerBookingFlow.choosing_main_service),
    F.data.startswith("book:main:"),
)
router.callback_query.register(
    handle_addon_selected,
    StateFilter(CustomerBookingFlow.choosing_addons),
    F.data.startswith("book:addon:"),
)
router.callback_query.register(
    handle_addons_done,
    StateFilter(CustomerBookingFlow.choosing_addons),
    F.data == ADDONS_DONE_CALLBACK,
)
router.callback_query.register(
    handle_date_selected,
    StateFilter(CustomerBookingFlow.choosing_date),
    F.data.startswith("book:date:"),
)
router.callback_query.register(
    handle_slot_selected,
    StateFilter(CustomerBookingFlow.choosing_slot),
    F.data.startswith("book:slot:"),
)
router.message.register(handle_name_received, StateFilter(CustomerBookingFlow.waiting_for_name))
router.message.register(handle_phone_received, StateFilter(CustomerBookingFlow.waiting_for_phone))
router.message.register(
    handle_vehicle_plate_received,
    StateFilter(CustomerBookingFlow.waiting_for_vehicle_plate),
)
router.callback_query.register(
    handle_booking_confirmed,
    StateFilter(CustomerBookingFlow.confirming),
    F.data == CONFIRM_BOOKING_CALLBACK,
)
router.callback_query.register(
    handle_change_time,
    StateFilter(CustomerBookingFlow.confirming),
    F.data == CHANGE_TIME_CALLBACK,
)
router.callback_query.register(
    handle_change_services,
    StateFilter(CustomerBookingFlow.confirming, CustomerBookingFlow.choosing_date),
    F.data == CHANGE_SERVICES_CALLBACK,
)
router.callback_query.register(
    handle_cancel_flow,
    StateFilter(
        CustomerBookingFlow.choosing_main_service,
        CustomerBookingFlow.choosing_addons,
        CustomerBookingFlow.choosing_date,
        CustomerBookingFlow.choosing_slot,
        CustomerBookingFlow.waiting_for_name,
        CustomerBookingFlow.waiting_for_phone,
        CustomerBookingFlow.waiting_for_vehicle_plate,
        CustomerBookingFlow.confirming,
    ),
    F.data == CANCEL_FLOW_CALLBACK,
)
