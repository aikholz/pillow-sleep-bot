from aiogram import F, Router
from aiogram.types import Message

from bot.database.db import (
    get_user, get_user_statistics, get_checkins_for_analysis, is_course_completed,
)
from bot.logic.lifecycle import evaluate_progress, stabilization_countdown
from bot.logic.sqi import compute_improvement
from bot.logic.sleep_model import build_sleep_profile

router = Router()


@router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message):
    telegram_id = message.from_user.id
    user = get_user(telegram_id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    _, name, age, category, schedule = user
    rows = get_checkins_for_analysis(telegram_id)
    stats = get_user_statistics(telegram_id)
    days, avg_sleep, avg_quality, avg_mood, avg_energy, nap_days, avg_stress = stats

    if days == 0:
        await message.answer("📊 Пока статистики нет. Сначала заполни чек-ин 😴")
        return

    profile = build_sleep_profile(rows, age, schedule or "")
    imp = compute_improvement(rows, profile.get("personal_target"))
    status = evaluate_progress(telegram_id)
    cd = stabilization_countdown(telegram_id)
    course_done = is_course_completed(telegram_id)

    text = f"📊 ТВОЯ СТАТИСТИКА\n\n👤 {name}\n📅 Заполнено дней: {days}\n\n"

    if avg_sleep is not None:
        text += f"😴 Средний сон: {avg_sleep:.1f} ч (цель: {profile.get('personal_target', 8.0):.1f} ч)\n"
    if avg_quality is not None:
        text += f"⭐ Качество: {avg_quality:.1f}/5\n"
    if avg_mood is not None:
        text += f"🙂 Настроение: {avg_mood:.1f}/5\n"
    if avg_energy is not None:
        text += f"⚡ Энергия: {avg_energy:.1f}/5\n"
    if avg_stress is not None:
        text += f"😰 Стресс: {avg_stress:.1f}/5\n"

    if imp:
        arrow = "📈" if imp["delta_pct"] > 0 else "📉"
        text += (
            f"\n{arrow} SQI сна: {imp['start_sqi']:.0f} → {imp['end_sqi']:.0f} "
            f"({imp['delta_pct']:+.0f}%)\n"
            f"💡 Привычки: {imp['habits_pct']:+.0f}%\n"
        )

    if course_done:
        text += "\n🎉 Курс завершён — результат закреплён!\n"
        text += "Ты можешь продолжать вести дневник: данные помогают поддерживать форму."
    else:
        text += "\n🎯 Твой этап:\n"
        phase_labels = {
            "collecting": "📦 Сбор данных — нужно ещё немного дней для базовой линии.",
            "baseline": "📐 Формируем базовую линию твоего сна.",
            "improving": "🚀 Есть прогресс! Закрепляем привычки.",
            "stabilizing": "🔒 Стабилизация результата.",
            "completed": "🎉 Курс завершён — результат закреплён!",
            "regression": "🔧 Небольшой откат — поможем вернуться к росту.",
        }
        text += phase_labels.get(status, status) + "\n"

        if cd:
            left, total = cd
            if left > 0:
                text += f"⏳ До закрытия курса: {left} дн. из {total}."
            else:
                text += "⏳ Стабилизация завершена — курс закрыт."

    await message.answer(text)