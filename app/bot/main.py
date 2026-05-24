import asyncio
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.factory import create_bot, create_dispatcher
from app.config import Settings
from app.db.session import create_sessionmaker


@dataclass(frozen=True, slots=True)
class BotRuntime:
    bot: Bot
    dispatcher: Dispatcher
    sessionmaker: async_sessionmaker[AsyncSession]


def build_runtime(settings: Settings) -> BotRuntime:
    sessionmaker = create_sessionmaker(str(settings.database_url))
    return BotRuntime(
        bot=create_bot(settings),
        dispatcher=create_dispatcher(settings=settings, sessionmaker=sessionmaker),
        sessionmaker=sessionmaker,
    )


async def run_polling(settings: Settings | None = None) -> None:
    runtime_settings = settings if settings is not None else Settings()  # type: ignore[call-arg]
    runtime = build_runtime(runtime_settings)
    try:
        await runtime.dispatcher.start_polling(runtime.bot)
    finally:
        await runtime.bot.session.close()


def main() -> None:
    asyncio.run(run_polling())


if __name__ == "__main__":
    main()
