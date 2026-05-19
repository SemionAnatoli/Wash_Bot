from aiogram import Dispatcher
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.dependencies import CustomerBookingServiceMiddleware
from app.bot.factory import create_bot, create_dispatcher
from app.config import Settings


def test_create_dispatcher_registers_default_booking_context() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
        default_car_wash_id=10,
        default_branch_id=20,
    )
    dispatcher = create_dispatcher(
        settings=settings,
        sessionmaker=async_sessionmaker(class_=AsyncSession),
    )

    assert isinstance(dispatcher, Dispatcher)
    assert dispatcher["settings"] is settings
    assert dispatcher["default_car_wash_id"] == 10
    assert dispatcher["default_branch_id"] == 20
    assert any(router.name == "customer_booking" for router in dispatcher.sub_routers)
    assert any(
        isinstance(middleware, CustomerBookingServiceMiddleware)
        for middleware in dispatcher.update.middleware._middlewares
    )


def test_create_bot_configures_html_parse_mode() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="123456:ABCDEF",
        default_car_wash_id=10,
        default_branch_id=20,
    )

    bot = create_bot(settings)

    assert bot.default.parse_mode == ParseMode.HTML
