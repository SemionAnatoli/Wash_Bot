from datetime import date, datetime
from decimal import Decimal

from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CANCEL_ACTIVE_BOOKING_CALLBACK,
    CANCEL_FLOW_CALLBACK,
    CHANGE_SERVICES_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
    MY_ACTIVE_BOOKING_CALLBACK,
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
from app.services.customer_booking import ServiceOption


def option(service_id: int, title: str, *, is_addon: bool = False) -> ServiceOption:
    return ServiceOption(
        id=service_id,
        title=title,
        category="addon" if is_addon else "wash",
        price=Decimal("100"),
        duration_minutes=30,
        is_addon=is_addon,
    )


def callback_grid(markup) -> list[list[str]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


def text_grid(markup) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.inline_keyboard]


def test_booking_entry_keyboard_contains_start_action() -> None:
    markup = booking_entry_keyboard()

    assert callback_grid(markup) == [[BOOKING_START_CALLBACK], [MY_ACTIVE_BOOKING_CALLBACK]]
    assert text_grid(markup) == [["Записаться"], ["Моя запись"]]


def test_active_booking_keyboard_contains_cancel_action() -> None:
    markup = active_booking_keyboard()

    assert callback_grid(markup) == [[CANCEL_ACTIVE_BOOKING_CALLBACK]]
    assert text_grid(markup) == [["Отменить запись"]]


def test_main_services_keyboard_uses_service_callbacks() -> None:
    markup = main_services_keyboard([option(3, "Стандарт")])

    assert callback_grid(markup) == [["book:main:3"]]
    assert text_grid(markup) == [["Стандарт — 100 руб., 30 мин"]]


def test_service_keyboard_text_keeps_readable_special_characters() -> None:
    markup = main_services_keyboard([option(3, "Wash <Pro> & Wax")])
    text = text_grid(markup)[0][0]

    assert "Wash <Pro> & Wax" in text
    assert "&lt;" not in text
    assert "&amp;" not in text


def test_addons_keyboard_marks_selected_addons_and_has_continue() -> None:
    markup = addons_keyboard(
        [option(5, "Воск", is_addon=True), option(6, "Чернение шин", is_addon=True)],
        selected_ids={5},
    )

    assert callback_grid(markup) == [
        ["book:addon:5"],
        ["book:addon:6"],
        [ADDONS_DONE_CALLBACK],
    ]
    assert text_grid(markup)[0] == ["✓ Воск — 100 руб., 30 мин"]
    assert text_grid(markup)[2] == ["Продолжить"]


def test_date_and_slot_keyboards_use_stable_callbacks() -> None:
    dates = [date(2026, 5, 18), date(2026, 5, 19)]
    slots = [datetime(2026, 5, 18, 10), datetime(2026, 5, 18, 10, 30)]

    assert callback_grid(date_keyboard(dates)) == [
        ["book:date:2026-05-18"],
        ["book:date:2026-05-19"],
    ]
    assert callback_grid(slots_keyboard(slots)) == [
        ["book:slot:2026-05-18T10:00"],
        ["book:slot:2026-05-18T10:30"],
    ]


def test_no_slots_keyboard_offers_dates_change_services_and_cancel() -> None:
    dates = [date(2026, 5, 18), date(2026, 5, 19)]
    markup = no_slots_keyboard(dates)

    assert callback_grid(markup) == [
        ["book:date:2026-05-18"],
        ["book:date:2026-05-19"],
        [CHANGE_SERVICES_CALLBACK],
        [CANCEL_FLOW_CALLBACK],
    ]
    assert text_grid(markup)[2:] == [["Изменить услуги"], ["Отменить"]]


def test_confirmation_keyboard_contains_confirm_and_recovery_actions() -> None:
    markup = confirmation_keyboard()

    assert callback_grid(markup) == [
        [CONFIRM_BOOKING_CALLBACK],
        ["book:change_time"],
        ["book:change_services"],
        ["book:cancel_flow"],
    ]
