from datetime import datetime

from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CANCEL_ACTIVE_BOOKING_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
    MY_ACTIVE_BOOKING_CALLBACK,
    build_addon_callback,
    build_date_callback,
    build_main_service_callback,
    build_slot_callback,
    parse_id_callback,
    parse_slot_callback,
)


def test_booking_callback_builders_are_stable() -> None:
    assert BOOKING_START_CALLBACK == "book:start"
    assert MY_ACTIVE_BOOKING_CALLBACK == "book:my_active"
    assert CANCEL_ACTIVE_BOOKING_CALLBACK == "book:cancel_active"
    assert ADDONS_DONE_CALLBACK == "book:addons_done"
    assert CONFIRM_BOOKING_CALLBACK == "book:confirm"
    assert build_main_service_callback(12) == "book:main:12"
    assert build_addon_callback(7) == "book:addon:7"
    assert build_date_callback("2026-05-18") == "book:date:2026-05-18"
    assert build_slot_callback(datetime(2026, 5, 18, 10, 30)) == "book:slot:2026-05-18T10:30"


def test_callback_parsers_return_typed_values() -> None:
    assert parse_id_callback("book:main:12", prefix="book:main") == 12
    assert parse_id_callback("book:addon:7", prefix="book:addon") == 7
    assert parse_slot_callback("book:slot:2026-05-18T10:30") == datetime(2026, 5, 18, 10, 30)
