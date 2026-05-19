from aiogram import Dispatcher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.factory import create_dispatcher
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
