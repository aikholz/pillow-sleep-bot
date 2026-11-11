import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from bot.handlers.charts import router as charts_router
from bot.handlers.recommendations import router as recommendations_router
from bot.handlers.analysis import router as analysis_router
from bot.handlers.report import router as report_router
from bot.handlers.start import router as start_router
from bot.handlers.registration import router as registration_router
from bot.handlers.checkin import router as checkin_router
from bot.handlers.statistics import router as statistics_router
from bot.handlers.help import router as help_router
from bot.handlers.admin import router as admin_router
from bot.database.db import init_db
from bot.notifications import daily_reminder_loop
from bot.handlers.export import router as export_router
from bot.handlers.facts import router as facts_router
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main():
    if not TOKEN:
        raise ValueError("Не найден BOT_TOKEN в файле .env")

    init_db()

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(registration_router)
    dp.include_router(checkin_router)
    dp.include_router(statistics_router)
    dp.include_router(report_router)
    dp.include_router(analysis_router)
    dp.include_router(recommendations_router)
    dp.include_router(charts_router)
    dp.include_router(export_router)
    dp.include_router(help_router)
    dp.include_router(facts_router)
    dp.include_router(admin_router)

    # Фоновая задача с ежедневным напоминанием в 09:00
    asyncio.create_task(daily_reminder_loop(bot))

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
    except Exception as e:
        logger.exception(f"Ошибка при запуске бота: {e}")