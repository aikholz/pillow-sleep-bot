from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from datetime import date, timedelta

from bot.database.db import (
    get_all_users,
    get_active_users_count,
    get_top_users,
    get_recent_users,
)


router = Router()

ADMIN_ID = 1096737314


@router.message(Command("stats"), F.from_user.id == ADMIN_ID)
async def show_admin_stats(message: Message):
    total = len(get_all_users())
    active_7 = get_active_users_count(days=7)
    active_30 = get_active_users_count(days=30)
    top = get_top_users(limit=5)
    recent = get_recent_users(limit=5)

    text = (
        "📊 СТАТИСТИКА БОТА «ПОДУШКА»\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"🔥 Активных за 7 дней: {active_7}\n"
        f"📅 Активных за 30 дней: {active_30}\n\n"
    )

    if top:
        text += "🏆 ТОП-5 АКТИВНЫХ\n\n"
        for i, (name, count) in enumerate(top, start=1):
            text += f"{i}. {name} — {count} чек-инов\n"
        text += "\n"

    if recent:
        text += "🆕 ПОСЛЕДНИЕ 5\n\n"
        for name, age, category, created_at in recent:
            short_cat = category.split("/")[0].strip()
            text += f"• {name}, {age} лет — {short_cat}\n"

    await message.answer(text)