from app.bot.admin_bookings.callbacks import (
    ADMIN_TODAY_CALLBACK,
    build_admin_cancel_callback,
    build_admin_confirm_callback,
)
from app.bot.admin_bookings.keyboards import admin_booking_actions_keyboard, admin_today_keyboard


def callback_grid(markup) -> list[list[str]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


def text_grid(markup) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.inline_keyboard]


def test_pending_booking_keyboard_contains_confirm_cancel_and_today() -> None:
    markup = admin_booking_actions_keyboard(booking_id=15, status="pending")

    assert callback_grid(markup) == [
        [build_admin_confirm_callback(15)],
        [build_admin_cancel_callback(15)],
        [ADMIN_TODAY_CALLBACK],
    ]
    assert text_grid(markup) == [["Подтвердить"], ["Отменить"], ["Сегодня"]]


def test_confirmed_booking_keyboard_contains_cancel_and_today() -> None:
    markup = admin_booking_actions_keyboard(booking_id=15, status="confirmed")

    assert callback_grid(markup) == [[build_admin_cancel_callback(15)], [ADMIN_TODAY_CALLBACK]]
    assert text_grid(markup) == [["Отменить"], ["Сегодня"]]


def test_terminal_booking_keyboard_contains_today_only() -> None:
    markup = admin_booking_actions_keyboard(booking_id=15, status="completed")

    assert callback_grid(markup) == [[ADMIN_TODAY_CALLBACK]]
    assert text_grid(markup) == [["Сегодня"]]


def test_admin_today_keyboard_contains_today_action() -> None:
    markup = admin_today_keyboard()

    assert callback_grid(markup) == [[ADMIN_TODAY_CALLBACK]]
    assert text_grid(markup) == [["Сегодня"]]
