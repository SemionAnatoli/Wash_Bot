from collections.abc import Iterable
from datetime import date, datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CANCEL_ACTIVE_BOOKING_CALLBACK,
    CANCEL_FLOW_CALLBACK,
    CHANGE_SERVICES_CALLBACK,
    CHANGE_TIME_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
    MY_ACTIVE_BOOKING_CALLBACK,
    build_addon_callback,
    build_date_callback,
    build_main_service_callback,
    build_slot_callback,
)
from app.bot.customer_booking.messages import service_line
from app.services.customer_booking import ServiceOption


def _markup(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def booking_entry_keyboard() -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text="Записаться",
                    callback_data=BOOKING_START_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Моя запись",
                    callback_data=MY_ACTIVE_BOOKING_CALLBACK,
                )
            ],
        ]
    )


def active_booking_keyboard() -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text="Отменить запись",
                    callback_data=CANCEL_ACTIVE_BOOKING_CALLBACK,
                )
            ]
        ]
    )


def main_services_keyboard(services: Iterable[ServiceOption]) -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text=service_line(service),
                    callback_data=build_main_service_callback(service.id),
                )
            ]
            for service in services
        ]
    )


def addons_keyboard(
    addons: Iterable[ServiceOption],
    *,
    selected_ids: set[int] | None = None,
) -> InlineKeyboardMarkup:
    selected_ids = selected_ids or set()
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✓ ' if addon.id in selected_ids else ''}{service_line(addon)}",
                callback_data=build_addon_callback(addon.id),
            )
        ]
        for addon in addons
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="Продолжить",
                callback_data=ADDONS_DONE_CALLBACK,
            )
        ]
    )
    return _markup(rows)


def date_keyboard(dates: Iterable[date]) -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text=day.strftime("%d.%m.%Y"),
                    callback_data=build_date_callback(day.isoformat()),
                )
            ]
            for day in dates
        ]
    )


def no_slots_keyboard(dates: Iterable[date]) -> InlineKeyboardMarkup:
    rows = date_keyboard(dates).inline_keyboard
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="Изменить услуги",
                    callback_data=CHANGE_SERVICES_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отменить",
                    callback_data=CANCEL_FLOW_CALLBACK,
                )
            ],
        ]
    )
    return _markup(rows)


def slots_keyboard(slots: Iterable[datetime]) -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text=slot.strftime("%H:%M"),
                    callback_data=build_slot_callback(slot),
                )
            ]
            for slot in slots
        ]
    )


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=CONFIRM_BOOKING_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Выбрать другое время",
                    callback_data=CHANGE_TIME_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Изменить услуги",
                    callback_data=CHANGE_SERVICES_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отменить",
                    callback_data=CANCEL_FLOW_CALLBACK,
                )
            ],
        ]
    )
