from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.admin_bookings.handlers import router as admin_bookings_router
from app.bot.customer_booking.handlers import router as customer_booking_router
from app.bot.dependencies import CustomerBookingServiceMiddleware
from app.config import Settings


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    *,
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher["settings"] = settings
    dispatcher["default_car_wash_id"] = settings.default_car_wash_id
    dispatcher["default_branch_id"] = settings.default_branch_id
    dispatcher["admin_telegram_ids"] = settings.admin_telegram_ids
    dispatcher.update.middleware(CustomerBookingServiceMiddleware(sessionmaker))
    dispatcher.include_router(customer_booking_router)
    dispatcher.include_router(admin_bookings_router)
    return dispatcher
