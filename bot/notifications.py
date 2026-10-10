import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot

from bot.database.db import get_all_users


logger = logging.getLogger(__name__)


REMINDER_HOUR = 9      # 9 утра
REMINDER_MINUTE = 0    # ровно в 09:00


REMINDER_TEXT = (
    "☀️ Доброе утро!\n\n"
    "Не забудь отметить прошедший день 😴\n\n"
    "Нажми «😴 Отметить сон», чтобы заполнить чек-ин.\n"
    "Это займёт меньше минуты, а «Подушка» станет "
    "точнее в рекомендациях."
)


async def send_daily_reminders(bot: Bot):
    """Рассылает напоминание всем пользователям."""
    user_ids = get_all_users()

    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=REMINDER_TEXT,
            )
        except Exception as e:
            logger.warning(
                f"Не удалось отправить напоминание "
                f"пользователю {user_id}: {e}"
            )


def seconds_until_next_reminder() -> float:
    """Сколько секунд ждать до следующего 09:00."""
    now = datetime.now()
    next_run = now.replace(
        hour=REMINDER_HOUR,
        minute=REMINDER_MINUTE,
        second=0,
        microsecond=0,
    )

    if next_run <= now:
        next_run += timedelta(days=1)

    return (next_run - now).total_seconds()


async def daily_reminder_loop(bot: Bot):
    """Бесконечный цикл: ждём до 09:00 и рассылаем."""
    while True:
        delay = seconds_until_next_reminder()
        logger.info(
            f"Следующее напоминание через "
            f"{delay / 3600:.1f} ч"
        )
        await asyncio.sleep(delay)

        try:
            await send_daily_reminders(bot)
            logger.info("Ежедневные напоминания отправлены")
        except Exception as e:
            logger.exception(f"Ошибка при рассылке напоминаний: {e}")

        # Небольшая пауза, чтобы не запуститься дважды в одну минуту
        await asyncio.sleep(60)