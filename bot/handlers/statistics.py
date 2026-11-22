# bot/handlers/statistics.py
from aiogram import F, Router
from aiogram.types import Message

from bot.database.db import (
    get_user, get_user_statistics, get_checkins_for_analysis, is_course_completed,
)
from bot.logic.lifecycle import evaluate_progress, stabilization_countdown
from bot.logic.sqi import compute_improvement, daily_sqi
from bot.logic.sleep_model import build_sleep_profile
from bot.logic.reminders import build_context, select_tips

router = Router()


@router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message):
    telegram_id = message.from_user.id
    user = get_user(telegram_id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    _, name, age, category, schedule = user
    schedule = schedule or ""
    category = category or ""

    rows = get_checkins_for_analysis(telegram_id)
    stats = get_user_statistics(telegram_id)
    days, avg_sleep, avg_quality, avg_mood, avg_energy, nap_days, avg_stress = stats

    if days == 0:
        await message.answer("📊 Пока статистики нет. Сначала заполни чек-ин 😴")
        return

    profile = build_sleep_profile(rows, age, schedule)
    target = profile.get("personal_target", 8.0)
    imp = compute_improvement(rows, target)
    status = evaluate_progress(telegram_id)
    cd = stabilization_countdown(telegram_id)
    course_done = is_course_completed(telegram_id)

    # ---------- ОСНОВНОЙ БЛОК ----------
    text = f"📊 ТВОЯ СТАТИСТИКА\n\n👤 {name}\n📅 Заполнено дней: {days}\n\n"

    if avg_sleep is not None:
        text += f"😴 Средний сон: {avg_sleep:.1f} ч (цель: {target:.1f} ч)\n"
    if avg_quality is not None:
        text += f"⭐ Качество: {avg_quality:.1f}/5\n"
    if avg_mood is not None:
        text += f"🙂 Настроение: {avg_mood:.1f}/5\n"
    if avg_energy is not None:
        text += f"⚡ Энергия: {avg_energy:.1f}/5\n"
    if avg_stress is not None:
        text += f"😰 Стресс: {avg_stress:.1f}/5\n"
    if nap_days:
        text += f"🌙 Дней с дневным сном: {int(nap_days)}\n"

    # ---------- SQI ----------
    if imp:
        arrow = "📈" if imp["delta_pct"] > 0 else ("📉" if imp["delta_pct"] < 0 else "➖")
        text += (
            f"\n{arrow} SQI сна: {imp['start_sqi']:.0f} → {imp['end_sqi']:.0f} "
            f"({imp['delta_pct']:+.0f}%)\n"
        )
        hab = imp["habits_pct"]
        if abs(hab) >= 1:
            text += f"💡 Привычки: {hab:+.0f}%\n"

    # ---------- ХУДШАЯ СМЕНА (если есть) ----------
    shift_groups = {}
    for r in rows:
        if len(r) > 12 and r[12] and r[0] is not None:
            shift_groups.setdefault(r[12], []).append(float(r[0]))
    if len(shift_groups) >= 2:
        worst_shift = min(shift_groups, key=lambda k: sum(shift_groups[k]) / len(shift_groups[k]))
        worst_avg = sum(shift_groups[worst_shift]) / len(shift_groups[worst_shift])
        text += f"\n🔄 Самая тяжёлая смена: «{worst_shift}» ({worst_avg:.1f} ч сна)\n"

    # ---------- ЭТАП ----------
    text += "\n───────────────\n"
    if course_done or status == "completed":
        text += "🏁 Этап: курс завершён — результат закреплён.\n"
    elif cd:
        left, total = cd
        if left > 0:
            text += (
                f"🔒 Этап: стабилизация ({left} из {total} дней осталось).\n"
                "Организм закрепляет новый режим.\n"
            )
        else:
            text += "🎉 Этап: стабилизация завершена!\n"
    elif status == "improving":
        text += "📈 Этап: улучшение — SQI растёт.\n"
    elif status == "regression":
        text += "📉 Этап: регресс — SQI снизился.\n"
    elif status == "baseline":
        text += "📊 Этап: сбор данных — пока не хватает динамики.\n"
    else:
        text += "📥 Этап: сбор данных.\n"

    # ---------- ХУДШИЙ / ЛУЧШИЙ ДЕНЬ (если данных ≥ 7) ----------
    if imp and len(rows) >= 7:
        scored = []
        for r in rows:
            sqi = daily_sqi(r, target)
            if sqi is not None:
                scored.append((sqi, r))
        if len(scored) >= 7:
            scored.sort(key=lambda x: x[0])
            worst, best = scored[0], scored[-1]

            def fmt(day):
                sqi, r = day
                sleep = r[0] if r[0] is not None else 0
                qual = r[1] if r[1] is not None else 0
                stress = r[4] if r[4] is not None else 0
                return f"SQI {sqi:.0f} (😴 {sleep:.1f} ч, ⭐ {qual}/5, 😰 {stress}/5)"

            text += (
                "\n───────────────\n"
                "🏁 ХУДШИЙ / ЛУЧШИЙ ДЕНЬ\n"
                f"🪫 Худший: {fmt(worst)}\n"
                f"⚡ Лучший: {fmt(best)}\n"
            )

    # ---------- 1 СОВЕТ (без дублирования полного списка) ----------
    if len(rows) >= 7:
        ctx = build_context(telegram_id, rows)
        # флаги графика
        ctx["is_shift"] = ("Сменный" in category) or ("Сменный" in schedule)
        ctx["is_night"] = ("Ночной" in category) or ("Ночной" in schedule) or ("ночной" in category.lower())
        ctx["is_student"] = "Учебный" in category or "Учебный" in schedule
        ctx["is_office"] = "Офисный" in category
        ctx["is_physical"] = "Физический" in category
        ctx["is_freelance"] = "Свободный" in category or "Свободный" in schedule
        ctx["total_sleep_mode"] = profile.get("total_sleep_mode", False)

        tips = select_tips(ctx, limit=1)
        if tips:
            text += "\n───────────────\n💡 Совет дня:\n" + tips[0] + "\n"

    # ---------- ОБЪЯСНЕНИЕ ----------
    text += (
        "\n───────────────\n"
        "🎯 Как считается улучшение\n"
        "SQI (0–100) объединяет 6 факторов: длительность сна "
        "относительно твоей цели, качество, энергию, настроение, "
        "стресс и привычки (кофеин, экран, активность, время сна).\n"
        "Бот сравнивает первые 7 дней и последние 7 дней.\n"
        "Улучшение фиксируется при +10% SQI "
        "(или +3% SQI, если привычки выросли на 15%+).\n"
        "После этого включается фаза стабилизации на 14 дней.\n"
    )

    await message.answer(text)