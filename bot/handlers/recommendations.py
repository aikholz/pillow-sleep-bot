from collections import defaultdict
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.types import Message

from bot.database.db import (
    get_user, get_user_statistics, get_checkins_for_analysis, get_checkins_for_period,
)
from bot.logic.sleep_model import (
    build_sleep_profile, nap_to_number, caffeine_to_number, screen_to_number,
    activity_to_number, caffeine_hours_before_sleep, analyze_circadian
)

router = Router()


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def analyze_causes(rows):
    scored = []
    for row in rows:
        if len(row) < 13 or row[0] is None: continue
        sleep, qual, mood, energy, stress = row[0], row[1], row[2], row[3], row[4]
        score_parts = []
        if qual is not None: score_parts.append((qual / 5) * 0.4)
        if energy is not None: score_parts.append((energy / 5) * 0.3)
        if mood is not None: score_parts.append((mood / 5) * 0.2)
        if stress is not None: score_parts.append(((5 - stress) / 4) * 0.1)
        if not score_parts: continue

        scored.append({
            "score": sum(score_parts) / sum([0.4, 0.3, 0.2, 0.1][:len(score_parts)]),
            "sleep": float(sleep),
            "caffeine": caffeine_to_number(row[5]),
            "screen": screen_to_number(row[7]),
            "activity": activity_to_number(row[8]),
            "sleep_time": row[11]
        })
    if len(scored) < 14: return []
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"best": scored[:7], "worst": scored[-7:], "all": scored}


def analyze_personal_optimum(rows, target_sleep):
    if target_sleep is None: return []
    lower, upper = target_sleep - 0.5, target_sleep + 0.5
    in_range, too_little = [], []
    for row in rows:
        if row[0] is None: continue
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
            f"🎯 Твой оптимум сна: {lower:.1f}–{upper:.1f} ч. В этом диапазоне энергия {avg_in:.1f}/5, а при недосыпе падает до {avg_low:.1f}/5.")
    return insights


def analyze_sleep_time(rows):
    """Анализ: ложится ли человек до 23:00."""
    early_sleep_qual, late_sleep_qual = [], []
    for row in rows:
        sleep_time_str = row[11]
        if not sleep_time_str: continue
        try:
            h, m = map(int, sleep_time_str.split(":"))
            if h < 12: h += 24
            if h < 23:
                early_sleep_qual.append(row[1])
            else:
                late_sleep_qual.append(row[1])
        except:
            pass

    insights = []
    avg_early = _avg(early_sleep_qual)
    avg_late = _avg(late_sleep_qual)
    if avg_early and avg_late and (avg_early - avg_late) > 0.5:
        insights.append(
            f"🌙 Ложись до 23:00. В дни, когда ты засыпал(а) раньше, качество сна было выше ({avg_early:.1f}/5 vs {avg_late:.1f}/5).")
    return insights


def analyze_shift_groups(rows):
    """Группирует сон по типам смен."""
    groups = defaultdict(list)
    for row in rows:
        if len(row) > 12 and row[12] is not None and row[0] is not None:
            groups[row[12]].append(float(row[0]))

    result = {}
    for shift, sleeps in groups.items():
        if sleeps:
            result[shift] = sum(sleeps) / len(sleeps)
    return result


@router.message(F.text == "💡 Рекомендации")
async def recommendations_handler(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    telegram_id, name, age, category, schedule = user
    rows = get_checkins_for_analysis(telegram_id)

    if not rows:
        await message.answer("Пока нет данных для рекомендаций. Заполни чек-ин 😴")
        return

    sleep_profile = build_sleep_profile(rows, age, schedule or "")
    target_sleep = sleep_profile.get("personal_target")

    text = "💡 Твои персональные советы\n\n"
    has_tips = False

    # 1. СОН И ОПТИМУМ
    optimum = analyze_personal_optimum(rows, target_sleep)
    if optimum:
        text += "\n".join(optimum) + "\n"
        has_tips = True

    # 2. ВРЕМЯ ОТХОДА КО СНУ (ДО 23:00)
    sleep_time_tips = analyze_sleep_time(rows)
    if sleep_time_tips:
        text += "\n".join(sleep_time_tips) + "\n"
        has_tips = True

    # 3. АНАЛИЗ ПРИЧИН (СРАВНЕНИЕ ХОРОШИХ И ПЛОХИХ ДНЕЙ)
    causes = analyze_causes(rows)
    if causes:
        best, worst = causes["best"], causes["worst"]
        all_days = causes["all"]

        # Проверка на пересып
        long_sleep_bad_days = [x for x in all_days if x["sleep"] > 9 and x["score"] < 0.6]
        if len(long_sleep_bad_days) >= 2:
            text += "⚠️ Пересып тоже вреден. В некоторые дни ты спал(а) больше 9 часов, но чувствовал(а) себя хуже обычного. Слишком долгий сон сбивает ритмы.\n"
            has_tips = True

        # Проверка на резкие перепады
        sleeps_all = [x["sleep"] for x in all_days]
        if max(sleeps_all) - min(sleeps_all) > 4:
            text += "⚠️ Резкие перепады сна. У тебя были дни по 4 часа и по 9+. Отсыпание не компенсирует недосып — мозг истощается.\n"
            has_tips = True

        # Кофеин
        b_caf, w_caf = _avg([x["caffeine"] for x in best]), _avg([x["caffeine"] for x in worst])
        if b_caf is not None and w_caf is not None and abs(b_caf - w_caf) >= 0.5:
            if b_caf < w_caf:
                text += f"☕ Сократи кофеин. В лучшие дни ты пил(а) {b_caf:.1f} порций, а в худшие — {w_caf:.1f}.\n"
            else:
                text += f"☕ Кофеин тебе не мешает. В лучшие дни ты пил(а) {b_caf:.1f} порций.\n"
            has_tips = True

        # Экран
        b_scr, w_scr = _avg([x["screen"] for x in best]), _avg([x["screen"] for x in worst])
        if b_scr is not None and w_scr is not None and abs(b_scr - w_scr) >= 0.5:
            if b_scr < w_scr:
                text += f"📱 Убери телефон перед сном. В лучшие дни экран был меньше ({b_scr:.1f} vs {w_scr:.1f} по шкале).\n"
            has_tips = True

        # Активность
        b_act, w_act = _avg([x["activity"] for x in best]), _avg([x["activity"] for x in worst])
        if b_act is not None and w_act is not None and abs(b_act - w_act) >= 0.5:
            if b_act > w_act:
                text += f"🏃 Добавь активности. В лучшие дни нагрузка была выше ({b_act:.1f} vs {w_act:.1f} по шкале).\n"
            has_tips = True

        # Сон
        b_slp, w_slp = _avg([x["sleep"] for x in best]), _avg([x["sleep"] for x in worst])
        if b_slp is not None and w_slp is not None and abs(b_slp - w_slp) >= 0.5:
            if b_slp > w_slp:
                text += f"😴 Ложись раньше. В лучшие дни ты спал(а) на {abs(b_slp - w_slp):.1f} ч больше.\n"
            has_tips = True

    # 4. ЦИРКАДНЫЙ АНАЛИЗ (короткий совет)
    period_start = date.today() - timedelta(days=30)
    circ_rows = get_checkins_for_period(telegram_id, str(period_start), str(date.today()))
    circ = analyze_circadian(circ_rows)
    if circ and circ["social_jetlag_hours"] > 1.5:
        text += f"\n🕐 Стабилизируй режим. Твой сдвиг сна на выходных — {circ['social_jetlag_hours']:.1f} ч. Старайся вставать в одно и то же время.\n"
        has_tips = True

    # 5. ПРОФЕССИОНАЛЬНЫЕ СОВЕТЫ
    if "Учебный" in category:
        # Считаем сон по уровням нагрузки
        strong_sleeps = [row[0] for row in rows if len(row) > 13 and row[13] == 2 and row[0]]
        none_sleeps = [row[0] for row in rows if len(row) > 13 and row[13] == 0 and row[0]]

        if strong_sleeps and none_sleeps:
            avg_strong = sum(strong_sleeps) / len(strong_sleeps)
            avg_none = sum(none_sleeps) / len(none_sleeps)
            diff = avg_none - avg_strong
            if diff > 0.5:
                text += f"\n📚 При сильной нагрузке ты спишь на {diff:.1f} ч меньше. Постарайся планировать дедлайны так, чтобы не жертвовать сном.\n"
            else:
                text += "\n📚 Ты хорошо справляешься с нагрузкой — сон почти не страдает.\n"
        else:
            text += "\n📚 Для учебы: старайся не сдвигать сон в выходные. Стабильное время подъема помогает концентрации.\n"
    elif "Сменный" in schedule or "Сменный" in category:
        text += "\n🔄 Для сменного графика: после ночной смены старайся спать в темной комнате. Свет сбивает выработку мелатонина.\n"
        has_tips = True
    elif "Ночной" in schedule or "Ночной" in category:
        text += "\n🌙 Для ночного графика: не пей кофе после 2-3 часов ночи, иначе не уснешь утром.\n"
        has_tips = True
    elif "Офисный" in category:
        text += "\n🧑‍💻 Для офисной работы: вставай из-за стола каждый час. Сидячий образ жизни ухудшает качество сна.\n"
        has_tips = True
    elif "Физический" in category:
        text += "\n🏃 Для физической работы: не тренируйся позже 3 часов до сна. Организм не успеет восстановиться.\n"
        has_tips = True
    elif "Свободный" in category:
        text += "\n🎨 Для свободного графика: ставь будильник на одно и то же время даже в выходные. Это стабилизирует циркадные ритмы.\n"
        has_tips = True

    # 6. СОВЕТЫ ПО ГРАФИКУ (самая тяжелая смена)
    shift_groups = analyze_shift_groups(rows)
    if shift_groups and len(shift_groups) > 1:
        worst_shift = min(shift_groups, key=shift_groups.get)
        worst_sleep = shift_groups[worst_shift]
        if worst_sleep < 6.5:
            text += f"\n🔄 Твоя самая тяжелая смена — «{worst_shift}» (в среднем {worst_sleep:.1f} ч сна). Подумай, как улучшить условия именно в эти дни.\n"
            has_tips = True

    if not has_tips:
        text += "Пока я не вижу явных закономерностей. Продолжай заполнять чек-ины, чтобы я смог дать точные советы на основе твоих данных."
    else:
        text += "\n⚠️ Это советы на основе твоих же данных. Они не заменяют консультацию врача."

    await message.answer(text)