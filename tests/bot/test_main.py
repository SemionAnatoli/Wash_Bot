from aiogram import Bot, Dispatcher

from app.bot.main import build_runtime
from app.config import Settings


async def test_build_runtime_creates_bot_dispatcher_and_sessionmaker() -> None:
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        telegram_bot_token="123456:ABCDEF",
        default_car_wash_id=10,
        default_branch_id=20,
        admin_telegram_ids=(1001,),
    )

    runtime = build_runtime(settings)
    try:
        assert isinstance(runtime.bot, Bot)
        assert isinstance(runtime.dispatcher, Dispatcher)
        assert runtime.dispatcher["settings"] is settings
        assert runtime.dispatcher["default_car_wash_id"] == 10
        assert runtime.dispatcher["default_branch_id"] == 20
        assert runtime.dispatcher["admin_telegram_ids"] == (1001,)
        assert runtime.sessionmaker is not None
    finally:
        await runtime.bot.session.close()
