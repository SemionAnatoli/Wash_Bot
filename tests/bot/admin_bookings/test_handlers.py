from datetime import date

from app.bot.admin_bookings.handlers import (
    handle_admin_booking_cancelled,
    handle_admin_booking_confirmed,
    handle_admin_today_requested,
    router,
)
from app.bot.admin_bookings.messages import (
    ADMIN_ACCESS_DENIED_TEXT,
    ADMIN_BOOKING_NOT_FOUND_TEXT,
    ADMIN_TODAY_EMPTY_TEXT,
)
from app.services.admin_booking import AdminBookingActionResult, AdminBookingActionStatus
from tests.bot.admin_bookings.fakes import (
    FakeAdminBookingService,
    FakeCallbackQuery,
    FakeTelegramUser,
    booking_details,
)


def first_text(callback: FakeCallbackQuery) -> str:
    assert callback.message is not None
    return callback.message.answers[0]["text"]


async def test_today_denies_non_admin() -> None:
    callback = FakeCallbackQuery(
        data="admin:today",
        from_user=FakeTelegramUser(id=2002),
    )
    service = FakeAdminBookingService(admin_ids={1001})

    await handle_admin_today_requested(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert callback.answered is True
    assert first_text(callback) == ADMIN_ACCESS_DENIED_TEXT
    assert service.today_requests == []


async def test_today_shows_admin_bookings() -> None:
    callback = FakeCallbackQuery(data="admin:today")
    service = FakeAdminBookingService(
        today_bookings=[
            booking_details(booking_id=15, status="pending"),
            booking_details(booking_id=16, status="confirmed", customer_name="Петр"),
        ]
    )

    await handle_admin_today_requested(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert service.today_requests == [{"car_wash_id": 10, "branch_id": 20, "today": date.today()}]
    assert "Сегодняшние записи" in first_text(callback)
    assert "#15" in first_text(callback)
    assert "#16" in first_text(callback)


async def test_today_empty_state() -> None:
    callback = FakeCallbackQuery(data="admin:today")
    service = FakeAdminBookingService(today_bookings=[])

    await handle_admin_today_requested(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert first_text(callback) == ADMIN_TODAY_EMPTY_TEXT


async def test_confirm_booking_changes_pending_for_admin() -> None:
    callback = FakeCallbackQuery(data="admin:confirm:15")
    service = FakeAdminBookingService()

    await handle_admin_booking_confirmed(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
    )

    assert service.confirm_requests == [{"car_wash_id": 10, "booking_id": 15}]
    assert "Запись подтверждена." in first_text(callback)
    assert "Подтверждена" in first_text(callback)
    assert callback.message is not None
    assert callback.message.answers[0]["reply_markup"] is not None


async def test_confirm_booking_denies_non_admin() -> None:
    callback = FakeCallbackQuery(
        data="admin:confirm:15",
        from_user=FakeTelegramUser(id=2002),
    )
    service = FakeAdminBookingService(admin_ids={1001})

    await handle_admin_booking_confirmed(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
    )

    assert first_text(callback) == ADMIN_ACCESS_DENIED_TEXT
    assert service.confirm_requests == []


async def test_cancel_booking_changes_active_for_admin() -> None:
    callback = FakeCallbackQuery(data="admin:cancel:15")
    service = FakeAdminBookingService()

    await handle_admin_booking_cancelled(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
    )

    assert service.cancel_requests == [{"car_wash_id": 10, "booking_id": 15}]
    assert "Запись отменена." in first_text(callback)
    assert "Отменена администратором" in first_text(callback)


async def test_stale_confirm_shows_current_state() -> None:
    callback = FakeCallbackQuery(data="admin:confirm:15")
    service = FakeAdminBookingService(
        confirm_result=AdminBookingActionResult(
            AdminBookingActionStatus.STALE,
            booking_details(status="confirmed"),
        )
    )

    await handle_admin_booking_confirmed(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
    )

    assert "Текущее состояние записи" in first_text(callback)
    assert "Подтверждена" in first_text(callback)


async def test_not_found_confirm_shows_safe_message() -> None:
    callback = FakeCallbackQuery(data="admin:confirm:15")
    service = FakeAdminBookingService(
        confirm_result=AdminBookingActionResult(AdminBookingActionStatus.NOT_FOUND, None)
    )

    await handle_admin_booking_confirmed(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
    )

    assert first_text(callback) == ADMIN_BOOKING_NOT_FOUND_TEXT


def test_admin_router_registers_callbacks() -> None:
    callback_names = [handler.callback.__name__ for handler in router.callback_query.handlers]

    assert callback_names == [
        "handle_admin_today_requested",
        "handle_admin_booking_confirmed",
        "handle_admin_booking_cancelled",
    ]
