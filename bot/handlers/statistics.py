from aiogram import F, Router
from aiogram.types import Message
from bot.database.db import get_user, get_user_statistics, get_checkins_for_analysis, get_user_status
from bot.logic.sleep_model import build_sleep_profile
from bot.logic.lifecycle import evaluate_progress

router = Router()


@router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message):
    telegram_id = message.from_user.id
    user = get_user(telegram_id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    _, name, age, category, schedule = user
    status = evaluate_progress(telegram_id)

    if status == "completed":
        text = (
            "🎉 **ПОЗДРАВЛЯЕМ! Твой курс завершен.**\n\n"
            "Ты прошел путь от первых замеров до стабильного качественного сна.\n\n"
            "📌 **Твои финальные рекомендации:**\n"
            "1. Ложись спать до 23:30.\n"
            "2. Сократи кофеин после 17:00.\n"
            "3. Убери экран за час до сна.\n\n"
            "Если захочешь пройти курс снова — просто напиши /start.\n"
            "До встречи!"
        )
        await message.answer(text)
        return

    statistics = get_user_statistics(telegram_id)
    (days, avg_sleep, avg_quality, avg_mood, avg_energy, nap_days, avg_stress) = statistics

    if days == 0:
        await message.answer("📊 Пока статистики нет. Сначала заполни чек-ин 😴")
        return

    text = f"📊 ТВОЯ СТАТИСТИКА\n\n👤 {name}\n📅 Заполнено дней: {days}\n\n"

    if avg_sleep is not None: text += f"😴 Средний сон: {avg_sleep:.1f} ч\n"
    if avg_quality is not None: text += f"⭐ Среднее качество: {avg_quality:.1f}/5\n"
    if avg_mood is not None: text += f"🙂 Среднее настроение: {avg_mood:.1f}/5\n"
    if avg_energy is not None: text += f"⚡ Средняя энергия: {avg_energy:.1f}/5\n"
    if avg_stress is not None: text += f"😰 Средний стресс: {avg_stress:.1f}/5\n"

    text += "\n\n🎯 **Твой прогресс:**\n"
    if status == "collecting":
        text += "Собираем данные для анализа (нужно 14 дней)."
    elif status == "analyzing":
        text += "Мы уже видим первые закономерности! Продолжай."
    elif status == "stabilizing":
        text += "Улучшения есть! Закрепляем результат (осталось пару дней)."
    else:
        text += "Курс завершен. Задача выполнена!"

    await message.answer(text)