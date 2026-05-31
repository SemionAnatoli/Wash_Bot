import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.factory import create_bot
from app.config import Settings
from app.db.session import create_sessionmaker
from app.worker.reminders import process_due_reminder_jobs

DEFAULT_POLL_INTERVAL_SECONDS = 30


class BotReminderGateway:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_message(self, telegram_id: int, text: str) -> None:
        await self._bot.send_message(chat_id=telegram_id, text=text)


@dataclass(frozen=True, slots=True)
class WorkerRuntime:
    bot: Bot
    sessionmaker: async_sessionmaker[AsyncSession]


def build_runtime(settings: Settings) -> WorkerRuntime:
    return WorkerRuntime(
        bot=create_bot(settings),
        sessionmaker=create_sessionmaker(str(settings.database_url)),
    )


async def run_reminder_worker(
    settings: Settings | None = None,
    *,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
) -> None:
    logger = logging.getLogger(__name__)
    runtime_settings = settings if settings is not None else Settings()  # type: ignore[call-arg]
    runtime = build_runtime(runtime_settings)
    gateway = BotReminderGateway(runtime.bot)
    try:
        while True:
            result = await process_due_reminder_jobs(
                runtime.sessionmaker,
                gateway,
                logger=logger,
            )
            if result.selected:
                logger.info(
                    "Processed reminder jobs: selected=%s claimed=%s sent=%s skipped=%s "
                    "failed=%s claim_missed=%s errors=%s",
                    result.selected,
                    result.claimed,
                    result.sent,
                    result.skipped,
                    result.failed,
                    result.claim_missed,
                    result.errors,
                )
            await asyncio.sleep(poll_interval_seconds)
    finally:
        await runtime.bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_reminder_worker())


if __name__ == "__main__":
    main()
