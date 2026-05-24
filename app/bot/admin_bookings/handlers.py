from datetime import date
from typing import cast

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot.admin_bookings.callbacks import ADMIN_TODAY_CALLBACK, parse_admin_booking_id
from app.bot.admin_bookings.keyboards import admin_booking_actions_keyboard
from app.bot.admin_bookings.messages import (
    ADMIN_ACCESS_DENIED_TEXT,
    ADMIN_BOOKING_CANCELLED_TEXT,
    ADMIN_BOOKING_CONFIRMED_TEXT,
    ADMIN_BOOKING_NOT_FOUND_TEXT,
    format_admin_booking_details,
    format_admin_today_bookings,
)
from app.services.admin_booking import (
    AdminBookingActionResult,
    AdminBookingActionStatus,
    AdminBookingService,
)


def _callback_message(callback: CallbackQuery) -> Message:
    if callback.message is None:
        raise RuntimeError("Callback query has no message.")
    return cast(Message, callback.message)


def _telegram_user_id(callback: CallbackQuery) -> int:
    if callback.from_user is None:
        raise RuntimeError("Telegram user is missing.")
    return callback.from_user.id


async def _ensure_admin(callback: CallbackQuery, service: AdminBookingService) -> bool:
    if service.is_admin(_telegram_user_id(callback)):
        return True
    await _callback_message(callback).answer(ADMIN_ACCESS_DENIED_TEXT)
    return False


async def handle_admin_today_requested(
    callback: CallbackQuery,
    *,
    admin_booking_service: AdminBookingService,
    default_car_wash_id: int,
    default_branch_id: int,
) -> None:
    await callback.answer()
    if not await _ensure_admin(callback, admin_booking_service):
        return

    bookings = await admin_booking_service.list_today_bookings(
        car_wash_id=default_car_wash_id,
        branch_id=default_branch_id,
        today=date.today(),
    )
    await _callback_message(callback).answer(format_admin_today_bookings(bookings))


def _action_text(result: AdminBookingActionResult, *, changed_text: str) -> str:
    if result.status == AdminBookingActionStatus.NOT_FOUND or result.booking is None:
        return ADMIN_BOOKING_NOT_FOUND_TEXT
    details = format_admin_booking_details(result.booking, title="Текущее состояние записи")
    if result.status == AdminBookingActionStatus.STALE:
        return details
    return f"{changed_text}\n\n{details}"


async def handle_admin_booking_confirmed(
    callback: CallbackQuery,
    *,
    admin_booking_service: AdminBookingService,
    default_car_wash_id: int,
) -> None:
    await callback.answer()
    if not await _ensure_admin(callback, admin_booking_service):
        return

    booking_id = parse_admin_booking_id(callback.data or "", prefix="admin:confirm")
    result = await admin_booking_service.confirm_booking(
        car_wash_id=default_car_wash_id,
        booking_id=booking_id,
    )
    await _callback_message(callback).answer(
        _action_text(result, changed_text=ADMIN_BOOKING_CONFIRMED_TEXT),
        reply_markup=_action_reply_markup(result),
    )


async def handle_admin_booking_cancelled(
    callback: CallbackQuery,
    *,
    admin_booking_service: AdminBookingService,
    default_car_wash_id: int,
) -> None:
    await callback.answer()
    if not await _ensure_admin(callback, admin_booking_service):
        return

    booking_id = parse_admin_booking_id(callback.data or "", prefix="admin:cancel")
    result = await admin_booking_service.cancel_booking(
        car_wash_id=default_car_wash_id,
        booking_id=booking_id,
    )
    await _callback_message(callback).answer(
        _action_text(result, changed_text=ADMIN_BOOKING_CANCELLED_TEXT),
        reply_markup=_action_reply_markup(result),
    )


def _action_reply_markup(result: AdminBookingActionResult) -> InlineKeyboardMarkup | None:
    if result.booking is None:
        return None
    return admin_booking_actions_keyboard(
        booking_id=result.booking.booking_id,
        status=result.booking.status,
    )


def create_router() -> Router:
    admin_router = Router(name="admin_bookings")
    admin_router.callback_query.register(
        handle_admin_today_requested,
        F.data == ADMIN_TODAY_CALLBACK,
    )
    admin_router.callback_query.register(
        handle_admin_booking_confirmed,
        F.data.startswith("admin:confirm:"),
    )
    admin_router.callback_query.register(
        handle_admin_booking_cancelled,
        F.data.startswith("admin:cancel:"),
    )
    return admin_router


router = create_router()
