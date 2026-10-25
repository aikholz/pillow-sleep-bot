from aiogram import F, Router
from aiogram.types import Message
from bot.database.db import get_user, get_user_statistics, get_checkins_for_analysis
from bot.logic.sleep_model import build_sleep_profile

router = Router()

@router.message(F.text == "📊 Моя статистика")
async def show_statistics(message: Message):
    telegram_id = message.from_user.id
    user = get_user(telegram_id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    _, name, age, category, schedule = user
    statistics = get_user_statistics(telegram_id)
    (days, avg_sleep, avg_quality, avg_mood, avg_energy, nap_days, avg_stress) = statistics

    if days == 0:
        await message.answer("📊 Пока статистики нет.\n\nСначала заполни хотя бы один чек-ин 😴")
        return

    text = f"📊 ТВОЯ СТАТИСТИКА\n\n👤 {name}\n📅 Заполнено дней: {days}\n\n"

    if avg_sleep is not None: text += f"😴 Средняя продолжительность сна: {avg_sleep:.1f} ч\n"
    if avg_quality is not None: text += f"⭐ Среднее качество сна: {avg_quality:.1f}/5\n"
    if avg_mood is not None: text += f"🙂 Среднее настроение: {avg_mood:.1f}/5\n"
    if avg_energy is not None: text += f"⚡ Средняя энергия: {avg_energy:.1f}/5\n"
    if avg_stress is not None: text += f"😰 Средний стресс: {avg_stress:.1f}/5\n"
    text += f"🌙 Дней с дневным сном: {nap_days}\n"

    # Оценка среднего сна
    if avg_sleep is not None:
        if avg_sleep < 6: text += "\n⚠️ Средняя продолжительность сна довольно низкая."
        elif avg_sleep < 7: text += "\n💡 Можно попробовать увеличить продолжительность сна."
        elif avg_sleep < 7.5: text += "\n💡 Сон находится около нижней границы возрастного ориентира."
        else: text += "\n✅ Средняя продолжительность сна выглядит достаточно стабильной."

    if avg_quality is not None and avg_quality < 3: text += "\n⭐ Средняя оценка качества сна низкая."
    if avg_stress is not None and avg_stress >= 4: text += "\n😰 Средний уровень стресса высокий."
    if avg_energy is not None and avg_energy <= 2: text += "\n⚡ Средняя дневная энергия низкая."

    # ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ (только суть)
    rows = get_checkins_for_analysis(telegram_id)
    sleep_profile = build_sleep_profile(rows, age)

    text += "\n\n🎯 ТВОЙ ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ СНА\n\n"

    if sleep_profile["mode"] in ("personal", "preliminary"):
        text += (
            f"Спать лучше всего в диапазоне {sleep_profile['zone_low']:.1f}–{sleep_profile['zone_high']:.1f} ч.\n"
            f"Достоверность паттерна: {sleep_profile['confidence']}."
        )
    else:
        text += "Пока мы используем возрастной ориентир. Продолжай заполнять чек-ины, чтобы я нашел твой личный диапазон."

    await message.answer(text)