from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.admin_bookings.notifier import AdminBookingNotifier
from app.services.admin_booking import AdminBookingService
from app.services.customer_booking import CustomerBookingService


class CustomerBookingServiceMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._sessionmaker() as session:
            data["db_session"] = session
            data["customer_booking_service"] = CustomerBookingService(session)
            admin_telegram_ids = tuple(data.get("admin_telegram_ids", ()))
            admin_booking_service = AdminBookingService(
                session,
                admin_telegram_ids=admin_telegram_ids,
            )
            data["admin_booking_service"] = admin_booking_service
            bot = data.get("bot")
            if isinstance(bot, Bot):
                data["admin_booking_notifier"] = AdminBookingNotifier(
                    bot=bot,
                    admin_booking_service=admin_booking_service,
                    admin_telegram_ids=admin_telegram_ids,
                )
            return await handler(event, data)
