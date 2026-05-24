from aiogram import Bot

from app.bot.admin_bookings.keyboards import admin_booking_actions_keyboard
from app.bot.admin_bookings.messages import format_admin_booking_details
from app.services.admin_booking import AdminBookingService


class AdminNotificationError(RuntimeError):
    """Raised when Telegram admin notification delivery fails."""


class AdminBookingNotifier:
    def __init__(
        self,
        *,
        bot: Bot,
        admin_booking_service: AdminBookingService,
        admin_telegram_ids: tuple[int, ...],
    ) -> None:
        self._bot = bot
        self._admin_booking_service = admin_booking_service
        self._admin_telegram_ids = admin_telegram_ids

    async def notify_new_booking(self, *, car_wash_id: int, booking_id: int) -> None:
        if not self._admin_telegram_ids:
            return

        booking = await self._admin_booking_service.get_booking_details(
            car_wash_id=car_wash_id,
            booking_id=booking_id,
        )
        if booking is None:
            return

        text = format_admin_booking_details(booking)
        reply_markup = admin_booking_actions_keyboard(
            booking_id=booking.booking_id,
            status=booking.status,
        )
        send_error: Exception | None = None
        for admin_id in self._admin_telegram_ids:
            try:
                await self._bot.send_message(admin_id, text, reply_markup=reply_markup)
            except Exception as exc:
                send_error = exc

        if send_error is not None:
            raise AdminNotificationError(
                "Failed to send admin booking notification."
            ) from send_error
