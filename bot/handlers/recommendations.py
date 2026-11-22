from collections import defaultdict
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.types import Message

from bot.database.db import (
    get_user, get_checkins_for_analysis, get_checkins_for_period,
)
from bot.logic.sleep_model import (
    build_sleep_profile, caffeine_to_number, screen_to_number,
    activity_to_number, analyze_circadian, analyze_schedule_insights,
)

router = Router()


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def analyze_causes(rows):
    scored = []
    for row in rows:
        if len(row) < 13 or row[0] is None:
            continue
        sleep, qual, mood, energy, stress = row[0], row[1], row[2], row[3], row[4]
        score_parts = []
        if qual is not None: score_parts.append((qual / 5) * 0.4)
        if energy is not None: score_parts.append((energy / 5) * 0.3)
        if mood is not None: score_parts.append((mood / 5) * 0.2)
        if stress is not None: score_parts.append(((5 - stress) / 4) * 0.1)
        if not score_parts:
            continue
        scored.append({
            "score": sum(score_parts) / sum([0.4, 0.3, 0.2, 0.1][:len(score_parts)]),
            "sleep": float(sleep),
            "quality": qual,
            "stress": stress,
            "caffeine": caffeine_to_number(row[5]),
            "screen": screen_to_number(row[7]),
            "activity": activity_to_number(row[8]),
            "sleep_time": row[11],
        })
    if len(scored) < 14:
        return None
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"best": scored[:7], "worst": scored[-7:], "all": scored}


def analyze_personal_optimum(rows, target_sleep):
    if target_sleep is None:
        return []
    lower, upper = target_sleep - 0.5, target_sleep + 0.5
    in_range, too_little = [], []
    for row in rows:
        if row[0] is None:
            continue
        s = float(row[0])
        if lower <= s <= upper and row[3]:
            in_range.append(float(row[3]))
        elif s < lower and row[3]:
            too_little.append(float(row[3]))

    insights = []
    avg_in = _avg(in_range)
    avg_low = _avg(too_little)
    if avg_in and avg_low and (avg_in - avg_low) > 0.5:
        insights.append(
            f"🎯 Твой оптимум сна: {lower:.1f}–{upper:.1f} ч. "
            f"В этом диапазоне энергия {avg_in:.1f}/5, а при недосыпе падает до {avg_low:.1f}/5."
        )
    return insights


def analyze_sleep_time(rows):
    early, late = [], []
    for row in rows:
        st = row[11]
        if not st:
            continue
        try:
            h, _ = map(int, st.split(":"))
            if h < 12:
                h += 24
            (early if h < 23 else late).append(row[1])
        except Exception:
            pass
    avg_early, avg_late = _avg(early), _avg(late)
    if avg_early and avg_late and (avg_early - avg_late) > 0.5:
        return [
            f"🌙 Ложись до 23:00. В дни, когда ты засыпал(а) раньше, "
            f"качество сна было выше ({avg_early:.1f}/5 vs {avg_late:.1f}/5)."
        ]
    return []


@router.message(F.text == "💡 Рекомендации")
async def recommendations_handler(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    telegram_id, name, age, category, schedule = user
    category = category or ""
    schedule = schedule or ""

    rows = get_checkins_for_analysis(telegram_id)
    if not rows:
        await message.answer("Пока нет данных для рекомендаций. Заполни чек-ин 😴")
        return

    sleep_profile = build_sleep_profile(rows, age, schedule)
    target_sleep = sleep_profile.get("personal_target")

    tips = []  # ← сюда собираем ВСЕ советы, потом нумеруем

    # 1. Персональный оптимум
    tips.extend(analyze_personal_optimum(rows, target_sleep))

    # 2. Время отхода ко сну
    tips.extend(analyze_sleep_time(rows))

    # 3. Анализ причин (лучшие / худшие дни)
    causes = analyze_causes(rows)
    if causes:
        best, worst = causes["best"], causes["worst"]
        all_days = causes["all"]

        # Пересып
        long_bad = [x for x in all_days if x["sleep"] > 9 and x["score"] < 0.6]
        if len(long_bad) >= 2:
            tips.append(
                "⚠️ Пересып тоже вреден. В некоторые дни ты спал(а) больше 9 часов, "
                "но чувствовал(а) себя хуже обычного — слишком долгий сон сбивает ритмы."
            )

        # Перепады
        sleeps_all = [x["sleep"] for x in all_days]
        if sleeps_all and max(sleeps_all) - min(sleeps_all) > 4:
            tips.append(
                "⚠️ Резкие перепады сна. У тебя были дни по 4 часа и по 9+. "
                "Отсыпание не компенсирует недосып."
            )

        # Кофеин
        b_caf = _avg([x["caffeine"] for x in best])
        w_caf = _avg([x["caffeine"] for x in worst])
        if b_caf is not None and w_caf is not None and abs(b_caf - w_caf) >= 0.5:
            if b_caf < w_caf:
                tips.append(
                    f"☕ Сократи кофеин. В лучшие дни ты пил(а) {b_caf:.1f} порций, "
                    f"а в худшие — {w_caf:.1f}."
                )
            else:
                tips.append(
                    f"☕ Кофеин тебе не мешает. В лучшие дни ты пил(а) {b_caf:.1f} порций."
                )

        # Экран
        b_scr, w_scr = _avg([x["screen"] for x in best]), _avg([x["screen"] for x in worst])
        if b_scr is not None and w_scr is not None and abs(b_scr - w_scr) >= 0.5 and b_scr < w_scr:
            tips.append(
                f"📱 Убери телефон перед сном. В лучшие дни экран был меньше "
                f"({b_scr:.1f} vs {w_scr:.1f} по шкале)."
            )

        # Активность
        b_act, w_act = _avg([x["activity"] for x in best]), _avg([x["activity"] for x in worst])
        if b_act is not None and w_act is not None and abs(b_act - w_act) >= 0.5 and b_act > w_act:
            tips.append(
                f"🏃 Добавь активности. В лучшие дни нагрузка была выше "
                f"({b_act:.1f} vs {w_act:.1f} по шкале)."
            )

        # Сон
        b_slp, w_slp = _avg([x["sleep"] for x in best]), _avg([x["sleep"] for x in worst])
        if b_slp is not None and w_slp is not None and abs(b_slp - w_slp) >= 0.5 and b_slp > w_slp:
            tips.append(
                f"😴 Ложись раньше. В лучшие дни ты спал(а) на {abs(b_slp - w_slp):.1f} ч больше."
            )

        # Общие
        avg_quality = _avg([x["quality"] for x in best] + [x["quality"] for x in worst])
        if avg_quality is not None and avg_quality < 3.0:
            tips.append("⭐ Обрати внимание на условия сна: температура, свет, шум.")

        avg_stress = _avg([x["stress"] for x in best] + [x["stress"] for x in worst])
        if avg_stress is not None and avg_stress >= 4.0:
            tips.append("😰 Стресс высокий. Попробуй дыхательные практики перед сном.")

        avg_act = _avg([x["activity"] for x in best] + [x["activity"] for x in worst])
        if avg_act is not None and avg_act < 1.5:
            tips.append("🏃 Добавь лёгкую прогулку за 2–3 часа до сна.")

        avg_scr = _avg([x["screen"] for x in best] + [x["screen"] for x in worst])
        if avg_scr is not None and avg_scr > 1.5:
            tips.append("📱 Экран перед сном мешает засыпанию. Попробуй читать книгу.")

        late_caf = [r for r in rows if r[6] and int(r[6].split(":")[0]) >= 17]
        if len(late_caf) >= 2:
            tips.append("☕ Кофеин вечером может ухудшить сон. Замени на травяной чай.")

    # 4. Циркадный анализ
    period_start = date.today() - timedelta(days=30)
    circ_rows = get_checkins_for_period(telegram_id, str(period_start), str(date.today()))
    circ = analyze_circadian(circ_rows)
    if circ and circ["social_jetlag_hours"] > 1.5:
        tips.append(
            f"🕐 Стабилизируй режим. Сдвиг сна на выходных — {circ['social_jetlag_hours']:.1f} ч. "
            "Старайся вставать в одно и то же время."
        )

    # 5. Сменный график: худшая смена
    shift_groups = defaultdict(list)
    for row in rows:
        if len(row) > 12 and row[12] and row[0]:
            shift_groups[row[12]].append(float(row[0]))

    if len(shift_groups) >= 2:
        worst_shift = min(shift_groups, key=lambda k: sum(shift_groups[k]) / len(shift_groups[k]))
        best_shift = max(shift_groups, key=lambda k: sum(shift_groups[k]) / len(shift_groups[k]))
        worst_avg = sum(shift_groups[worst_shift]) / len(shift_groups[worst_shift])
        best_avg = sum(shift_groups[best_shift]) / len(shift_groups[best_shift])
        if best_avg - worst_avg >= 1.0:
            tips.append(
                f"🔄 Самая тяжёлая смена — «{worst_shift}» (в среднем {worst_avg:.1f} ч сна), "
                f"а самая лёгкая — «{best_shift}» ({best_avg:.1f} ч). "
                f"Попробуй в дни «{worst_shift}» ложиться на полчаса раньше."
            )

    # 6. Советы по категории
    if "Сменный" in schedule or "Сменный" in category:
        tips.append(
            "🔄 При сменном графике не сбивай режим: даже если смена выпадает на ночь, "
            "в остальные дни ложись в одно и то же время."
        )
    elif "Ночной" in schedule or "Ночной" in category:
        tips.append(
            "🌙 При ночном графике используй свет: яркий свет в начале смены "
            "и темнота по пути домой помогут быстрее уснуть."
        )
    elif "Учебный" in category:
        tips.append(
            "📚 При учёбе не сдвигай сон в выходные более чем на 1 час, "
            "чтобы не сбить режим к понедельнику."
        )
    elif "Офисный" in category:
        tips.append(
            "🧑‍💻 При сидячей работе добавь короткую прогулку за 2–3 часа до сна — "
            "это улучшит качество отдыха."
        )
    elif "Физический" in category:
        tips.append(
            "🏃 При физической нагрузке заканчивай тренировки за 3 часа до сна, "
            "чтобы организм успел восстановиться."
        )

    # 7. НОВОЕ: аналитика по графику (ночной / офисный / свободный)
    schedule_text = analyze_schedule_insights(rows, category, schedule)
    if schedule_text:
        tips.append(schedule_text)

    # === ФИНАЛЬНЫЙ ВЫВОД (один раз, нумерованный) ===
    if not tips:
        await message.answer(
            "💡 Пока я не вижу явных закономерностей.\n\n"
            "Продолжай заполнять чек-ины — через 7–14 дней появятся персональные советы."
        )
        return

    lines = ["💡 ТВОИ ПЕРСОНАЛЬНЫЕ РЕКОМЕНДАЦИИ", ""]
    for i, t in enumerate(tips, 1):
        lines.append(f"{i}. {t}")
        lines.append("")
    lines.append("⚠️ Советы основаны на твоих данных и не заменяют консультацию врача.")

    await message.answer("\n".join(lines))