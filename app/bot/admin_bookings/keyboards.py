from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.admin_bookings.callbacks import (
    ADMIN_TODAY_CALLBACK,
    build_admin_cancel_callback,
    build_admin_confirm_callback,
)
from app.domain.statuses import BookingStatus


def _markup(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_booking_actions_keyboard(*, booking_id: int, status: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if status == BookingStatus.PENDING.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=build_admin_confirm_callback(booking_id),
                )
            ]
        )
    if status in {BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value}:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Отменить",
                    callback_data=build_admin_cancel_callback(booking_id),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Сегодня", callback_data=ADMIN_TODAY_CALLBACK)])
    return _markup(rows)


def admin_today_keyboard() -> InlineKeyboardMarkup:
    return _markup([[InlineKeyboardButton(text="Сегодня", callback_data=ADMIN_TODAY_CALLBACK)]])
