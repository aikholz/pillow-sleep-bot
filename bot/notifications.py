import asyncio
import logging
from datetime import datetime, timedelta, date

from aiogram import Bot

from bot.database.db import (
    get_all_users,
    get_users_without_recent_checkin,
    get_checkins_for_period,
)

logger = logging.getLogger(__name__)

REMINDER_HOUR = 9
REMINDER_MINUTE = 0

REMINDER_TEXT = (
    "☀️ Доброе утро!\n\n"
    "Не забудь отметить прошедший день 😴\n\n"
    "Нажми «😴 Мой сон», чтобы заполнить чек-ин."
)

INACTIVITY_TEXT = (
    "👋 Я заметил, что ты не заполнял(а) чек-ин 2 дня.\n\n"
    "Давай не терять прогресс! Заполни чек-ин за вчера — это займёт минуту 😴"
)

_last_inactivity_sent = {}


async def send_daily_reminders(bot: Bot):
    user_ids = get_all_users()
    for user_id in user_ids:
        try:
            await bot.send_message(chat_id=user_id, text=REMINDER_TEXT)
        except Exception as e:
            logger.warning(f"Не удалось отправить напоминание {user_id}: {e}")


async def send_inactivity_reminders(bot: Bot):
    today = date.today()
    user_ids = get_users_without_recent_checkin(days=2)
    for user_id in user_ids:
        last = _last_inactivity_sent.get(user_id)
        if last and (today - last).days < 3:
            continue
        try:
            await bot.send_message(chat_id=user_id, text=INACTIVITY_TEXT)
            _last_inactivity_sent[user_id] = today
        except Exception as e:
            logger.warning(f"Не удалось отправить inactivity {user_id}: {e}")


async def send_weekly_reports(bot: Bot):
    """Отправляет еженедельный отчет."""
    user_ids = get_all_users()
    for user_id in user_ids:
        try:
            end = date.today()
            start = end - timedelta(days=7)
            rows = get_checkins_for_period(user_id, str(start), str(end))

            if len(rows) < 3:
                continue

            sleeps = [r[1] for r in rows if r[1] is not None]
            qualities = [r[2] for r in rows if r[2] is not None]

            if not sleeps or not qualities:
                continue

            avg_sleep = sum(sleeps) / len(sleeps)
            avg_quality = sum(qualities) / len(qualities)

            text = (
                "📊 <b>Еженедельный отчет</b>\n\n"
                f"😴 Средний сон: {avg_sleep:.1f} ч\n"
                f"⭐ Среднее качество: {avg_quality:.1f}/5\n\n"
                "Продолжай в том же духе!"
            )
            await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Не удалось отправить weekly report {user_id}: {e}")


def seconds_until_next_reminder() -> float:
    now = datetime.now()
    next_run = now.replace(hour=REMINDER_HOUR, minute=REMINDER_MINUTE, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()


async def daily_reminder_loop(bot: Bot):
    while True:
        delay = seconds_until_next_reminder()
        logger.info(f"Следующее напоминание через {delay / 3600:.1f} ч")
        await asyncio.sleep(delay)
        try:
            await send_daily_reminders(bot)
            await send_inactivity_reminders(bot)

            # Еженедельный отчёт по понедельникам
            if datetime.now().weekday() == 0:
                await send_weekly_reports(bot)

            logger.info("Рассылка завершена")
        except Exception as e:
            logger.exception(f"Ошибка при рассылке: {e}")
        await asyncio.sleep(60)