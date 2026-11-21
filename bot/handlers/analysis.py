import math
from datetime import datetime
from aiogram import F, Router
from aiogram.types import Message
from bot.database.db import get_checkins_for_analysis, get_user

router = Router()


def average(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def correlation(x, y):
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 5:
        return None
    x_vals, y_vals = [p[0] for p in pairs], [p[1] for p in pairs]
    avg_x, avg_y = average(x_vals), average(y_vals)
    num = sum((a - avg_x) * (b - avg_y) for a, b in pairs)
    den_x = math.sqrt(sum((a - avg_x) ** 2 for a in x_vals))
    den_y = math.sqrt(sum((b - avg_y) ** 2 for b in y_vals))
    den = den_x * den_y
    return num / den if den != 0 else None


def strength_label(r):
    if r is None:
        return None
    value = abs(r)
    if value >= 0.7:
        return "сильная", "прямая" if r > 0 else "обратная"
    if value >= 0.5:
        return "умеренная", "прямая" if r > 0 else "обратная"
    if value >= 0.3:
        return "слабая", "прямая" if r > 0 else "обратная"
    return None


def plain_language(r, positive, negative):
    result = strength_label(r)
    if result is None:
        return None
    strength, direction = result
    text = positive if r > 0 else negative
    if strength == "сильная":
        conf = "Очень заметная закономерность."
    elif strength == "умеренная":
        conf = "Заметная закономерность."
    else:
        conf = "Слабая закономерность — могут быть исключения."
    return f"{text}\n   Сила связи: {strength} {direction}. {conf} (r={r:.2f})"


def caffeine_to_number(v):
    return {"Не пил(а)": 0, "1 чашка": 1, "2 чашки": 2, "3 и более": 3}.get(v, 0)


def screen_to_number(v):
    return {"Не смотрел(а)": 0, "До 30 минут": 1, "30–60 минут": 2, "Больше часа": 3}.get(v, 0)


def activity_to_number(v):
    return {"Не было": 0, "Лёгкая": 1, "Средняя": 2, "Высокая": 3}.get(v, 0)


def nap_to_number(v):
    return {None: 0, "До 30 минут": 0.5, "30–60 минут": 1, "Больше часа": 1.5}.get(v, 0)


def time_to_minutes(value):
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%H:%M")
        return dt.hour * 60 + dt.minute
    except ValueError:
        return None


def caffeine_hours_before_sleep(c_time, s_time):
    c_min, s_min = time_to_minutes(c_time), time_to_minutes(s_time)
    if c_min is None or s_min is None:
        return None
    diff = (s_min - c_min) % 1440
    return diff / 60


@router.message(F.text == "🔎 Анализ")
async def show_analysis(message: Message):
    telegram_id = message.from_user.id
    user = get_user(telegram_id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    _, name, age, category, schedule = user
    category = category or ""
    schedule = schedule or ""

    rows = get_checkins_for_analysis(telegram_id)

    if len(rows) < 5:
        await message.answer(
            "🔎 Для полноценного анализа пока недостаточно данных.\n\nНужно минимум 5 дней."
        )
        return

    # --- СБОР ДАННЫХ ---
    sleep, qual, mood, energy, stress = [], [], [], [], []
    caf, caf_time_val, screen, act, nap = [], [], [], [], []
    shift_groups = {}

    for row in rows:
        s, q, m, e, st = row[0], row[1], row[2], row[3], row[4]
        if s is not None:
            sleep.append(s)
        if q is not None:
            qual.append(q)
        if m is not None:
            mood.append(m)
        if e is not None:
            energy.append(e)
        if st is not None:
            stress.append(st)

        caf.append(caffeine_to_number(row[5]))
        screen.append(screen_to_number(row[7]))
        act.append(activity_to_number(row[8]))
        nap.append(nap_to_number(row[10]) if row[9] else 0)
        caf_time_val.append(caffeine_hours_before_sleep(row[6], row[11]))

        shift = row[12]
        if shift:
            if shift not in shift_groups:
                shift_groups[shift] = []
            shift_groups[shift].append(s)

    report = "🔎 АНАЛИЗ ТВОИХ ДАННЫХ\n\n"
    report += "📊 СРЕДНИЕ ПОКАЗАТЕЛИ\n"
    if average(sleep):
        report += f"😴 Сон: {average(sleep):.1f} ч\n"
    if average(qual):
        report += f"⭐ Качество: {average(qual):.1f}/5\n"
    if average(mood):
        report += f"🙂 Настроение: {average(mood):.1f}/5\n"
    if average(energy):
        report += f"⚡ Энергия: {average(energy):.1f}/5\n"
    if average(stress):
        report += f"😰 Стресс: {average(stress):.1f}/5\n"

    # --- ПРОФЕССИОНАЛЬНЫЕ ОТЛИЧИЯ ---
    report += "\n🧩 АНАЛИЗ ПО ТВОЕЙ КАТЕГОРИИ\n"
    if "Учебный" in category:
        none_load, medium_load, strong_load = [], [], []
        for row in rows:
            if len(row) > 13 and row[13] is not None and row[0] is not None:
                if row[13] == 0:
                    none_load.append(row[0])
                elif row[13] == 1:
                    medium_load.append(row[0])
                elif row[13] == 2:
                    strong_load.append(row[0])

        report += "📚 Твой сон в зависимости от учебной нагрузки:\n"
        if none_load:
            report += f"• Без учебы: {average(none_load):.1f} ч\n"
        if medium_load:
            report += f"• Средняя нагрузка: {average(medium_load):.1f} ч\n"
        if strong_load:
            report += f"• Сильная нагрузка: {average(strong_load):.1f} ч\n"

        if none_load and strong_load:
            diff = average(none_load) - average(strong_load)
            if diff > 0.5:
                report += f"⚠️ При сильной нагрузке ты спишь на {diff:.1f} ч меньше.\n"
    elif "Сменный" in category or "Ночной" in category.lower():
        report += "🌙 Для сменного графика важно следить за восстановлением после ночных смен.\n"
    elif "Офисный" in category:
        report += "🧑‍💻 Для умственной работы важна стабильность режима и качество сна.\n"
    elif "Физический" in category:
        report += "🏃 Для физической работы сон — главный инструмент восстановления.\n"
    elif "Свободный" in category:
        report += "🎨 Для свободного графика важно не сбивать циркадные ритмы.\n"

    # --- ОТЛИЧИЯ ПО ГРАФИКУ ---
    if shift_groups and len(shift_groups) > 1:
        report += "\n🔄 ТВОЙ СОН ПО ТИПАМ СМЕН\n"
        for shift, vals in shift_groups.items():
            if vals:
                report += f"• {shift}: {average(vals):.1f} ч\n"
    elif "Сменный" in schedule or "Ночной" in schedule:
        report += "\n🔄 Для анализа по сменам нужно больше дней. Заполняй чек-ин в разные смены.\n"

    # --- КОФЕИН И ВРЕМЯ ЗАСЫПАНИЯ ---
    sleep_with_caf, sleep_without_caf = [], []
    for row in rows:
        if row[0] is None:
            continue
        c_time = row[6]
        s_time = row[11]

        if c_time and s_time:
            h_c, m_c = map(int, c_time.split(":"))
            h_s, m_s = map(int, s_time.split(":"))
            s_min = h_s * 60 + m_s
            if s_min < 12 * 60:
                s_min += 24 * 60
            c_min = h_c * 60 + m_c
            if c_min < s_min:
                sleep_with_caf.append(s_min / 60)
            else:
                sleep_without_caf.append(s_min / 60)
        elif not c_time and s_time:
            h_s, m_s = map(int, s_time.split(":"))
            s_min = h_s * 60 + m_s
            if s_min < 12 * 60:
                s_min += 24 * 60
            sleep_without_caf.append(s_min / 60)

    if sleep_with_caf and sleep_without_caf:
        avg_caf = average(sleep_with_caf) % 24
        avg_no_caf = average(sleep_without_caf) % 24
        h_c, m_c = int(avg_caf), int((avg_caf - int(avg_caf)) * 60)
        h_n, m_n = int(avg_no_caf), int((avg_no_caf - int(avg_no_caf)) * 60)
        report += (
            f"\n☕ В дни с кофеином ты засыпаешь в среднем в {h_c:02d}:{m_c:02d}, "
            f"а без него — в {h_n:02d}:{m_n:02d}.\n"
        )

    # --- КОРРЕЛЯЦИИ ---
    pairs = [
        (correlation(caf, sleep), "☕→😴 Чем больше кофеина, тем дольше сон.",
         "☕→😴 Чем больше кофеина, тем короче сон."),
        (correlation(caf, qual), "☕→⭐ Чем больше кофеина, тем выше качество.",
         "☕→⭐ Чем больше кофеина, тем ниже качество."),
        (correlation(caf, mood), "☕→🙂 Кофеин улучшает настроение.",
         "☕→🙂 Кофеин ухудшает настроение."),
        (correlation(screen, sleep), "📱→😴 Экран связан с более долгим сном.",
         "📱→😴 Экран связан с более коротким сном."),
        (correlation(screen, qual), "📱→⭐ Экран связан с лучшим качеством.",
         "📱→⭐ Экран связан с худшим качеством."),
        (correlation(act, sleep), "🏃→😴 Активность связана с более долгим сном.",
         "🏃→😴 Активность связана с более коротким сном."),
        (correlation(act, qual), "🏃→⭐ Активность связана с лучшим качеством.",
         "🏃→⭐ Активность связана с худшим качеством."),
        (correlation(nap, sleep), "🌙→😴 Дневной сон связан с более долгим ночным.",
         "🌙→😴 Дневной сон связан с более коротким ночным."),
        (correlation(nap, qual), "🌙→⭐ Дневной сон связан с лучшим качеством.",
         "🌙→⭐ Дневной сон связан с худшим качеством."),
        (correlation(qual, mood), "⭐→🙂 Более высокое качество сна связано с лучшим настроением.",
         "⭐→🙂 Более высокое качество сна связано с худшим настроением."),
        (correlation(act, mood), "🏃→🙂 Физическая активность связана с лучшим настроением.",
         "🏃→🙂 Физическая активность связана с худшим настроением."),
        (correlation(stress, qual), "😰→⭐ Более высокий стресс связан с более высоким качеством сна.",
         "😰→⭐ Более высокий стресс связан с более низким качеством сна."),
    ]

    valid_caf = [v for v in caf_time_val if v is not None]
    if len(valid_caf) >= 5:
        r1 = correlation(caf_time_val, qual)
        if r1:
            pairs.append((
                r1,
                "⏰→⭐ Чем больше времени между кофеином и сном, тем выше качество.",
                "⏰→⭐ Чем ближе кофеин ко сну, тем выше качество.",
            ))
        r2 = correlation(caf_time_val, sleep)
        if r2:
            pairs.append((
                r2,
                "⏰→😴 Чем раньше кофеин, тем продолжительнее сон.",
                "⏰→😴 Чем раньше кофеин, тем короче сон.",
            ))

    observations = []
    for r, pos, neg in pairs:
        res = plain_language(r, pos, neg)
        if res:
            observations.append((abs(r), res))
    observations.sort(key=lambda x: x[0], reverse=True)

    report += "\n🔗 НАБЛЮДАЕМЫЕ СВЯЗИ\n"
    if observations:
        for _, text in observations[:7]:
            report += f"• {text}\n\n"
    else:
        report += "• Пока выраженных связей не обнаружено.\n"

    report += "\n📌 ИТОГ\nЭто наблюдаемые закономерности, а не диагноз."
    await message.answer(report)