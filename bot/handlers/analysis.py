import math
from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message

from bot.database.db import get_checkins_for_analysis


router = Router()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def average(values):
    values = [v for v in values if v is not None]

    if not values:
        return None

    return sum(values) / len(values)


def correlation(x, y):
    """Коэффициент корреляции Пирсона."""
    pairs = [
        (a, b)
        for a, b in zip(x, y)
        if a is not None and b is not None
    ]

    if len(pairs) < 5:
        return None

    x_values = [p[0] for p in pairs]
    y_values = [p[1] for p in pairs]

    avg_x = average(x_values)
    avg_y = average(y_values)

    numerator = sum(
        (a - avg_x) * (b - avg_y)
        for a, b in pairs
    )

    denominator_x = math.sqrt(
        sum((a - avg_x) ** 2 for a in x_values)
    )

    denominator_y = math.sqrt(
        sum((b - avg_y) ** 2 for b in y_values)
    )

    denominator = denominator_x * denominator_y

    if denominator == 0:
        return None

    return numerator / denominator


def strength_label(r):
    """
    Возвращает словесную оценку силы связи и её направления.
    """
    if r is None:
        return None

    value = abs(r)

    if value >= 0.7:
        strength = "сильная"
    elif value >= 0.5:
        strength = "умеренная"
    elif value >= 0.3:
        strength = "слабая"
    else:
        return None   # слишком слабая, не показываем

    if r > 0:
        direction = "прямая"
    else:
        direction = "обратная"

    return strength, direction


def plain_language(r, positive, negative):
    """
    Простое объяснение связи на человеческом языке.
    """
    result = strength_label(r)

    if result is None:
        return None

    strength, direction = result

    if r > 0:
        text = positive
    else:
        text = negative

    if strength == "сильная":
        confidence = "Очень заметная закономерность."
    elif strength == "умеренная":
        confidence = "Заметная закономерность."
    else:
        confidence = "Слабая закономерность — могут быть исключения."

    return (
        f"{text}\n"
        f"   Сила связи: {strength} {direction}. "
        f"{confidence} (r={r:.2f})"
    )


# ============================================================
# ПЕРЕВОДЫ ЗНАЧЕНИЙ
# ============================================================

def caffeine_to_number(value):
    return {
        "Не пил(а)": 0,
        "1 чашка": 1,
        "2 чашки": 2,
        "3 и более": 3,
    }.get(value, 0)


def screen_to_number(value):
    return {
        "Не смотрел(а)": 0,
        "До 30 минут": 1,
        "30–60 минут": 2,
        "Больше часа": 3,
    }.get(value, 0)


def activity_to_number(value):
    return {
        "Не было": 0,
        "Лёгкая": 1,
        "Средняя": 2,
        "Высокая": 3,
    }.get(value, 0)


def nap_to_number(value):
    return {
        None: 0,
        "До 30 минут": 0.5,
        "30–60 минут": 1,
        "Больше часа": 1.5,
    }.get(value, 0)


def time_to_minutes(value):
    if not value:
        return None

    try:
        dt = datetime.strptime(value, "%H:%M")
        return dt.hour * 60 + dt.minute
    except ValueError:
        return None


def caffeine_hours_before_sleep(caffeine_time, sleep_time):
    caffeine_minutes = time_to_minutes(caffeine_time)
    sleep_minutes = time_to_minutes(sleep_time)

    if caffeine_minutes is None or sleep_minutes is None:
        return None

    difference = (sleep_minutes - caffeine_minutes) % 1440

    if difference == 0:
        return 0

    return difference / 60


# ============================================================
# ОСНОВНОЙ ОБРАБОТЧИК
# ============================================================

@router.message(F.text == "🔎 Анализ")
async def show_analysis(message: Message):
    rows = get_checkins_for_analysis(message.from_user.id)

    if len(rows) < 5:
        await message.answer(
            "🔎 Для полноценного анализа пока недостаточно данных.\n\n"
            f"Заполнено дней: {len(rows)}\n"
            "Нужно минимум 5 дней.\n\n"
            "Продолжай заполнять ежедневный чек-ин 😴"
        )
        return

    sleep_values = []
    quality_values = []
    mood_values = []
    energy_values = []
    stress_values = []

    caffeine_values = []
    caffeine_before_sleep_values = []

    screen_values = []
    activity_values = []
    nap_values = []

    for row in rows:
        (
            sleep,
            quality,
            mood,
            energy,
            stress,
            caffeine,
            caffeine_time,
            screen,
            activity,
            nap_taken,
            nap_duration,
            sleep_time,
        ) = row

        sleep_values.append(sleep)
        quality_values.append(quality)
        mood_values.append(mood)
        energy_values.append(energy)

        if stress is not None:
            stress_values.append(stress)

        caffeine_values.append(
            caffeine_to_number(caffeine)
        )

        screen_values.append(
            screen_to_number(screen)
        )

        activity_values.append(
            activity_to_number(activity)
        )

        nap_values.append(
            nap_to_number(nap_duration)
        )

        caffeine_before_sleep = caffeine_hours_before_sleep(
            caffeine_time,
            sleep_time
        )

        caffeine_before_sleep_values.append(
            caffeine_before_sleep
        )

    # --------------------------------------------------------
    # ЗАГОЛОВОК И ПОЯСНЕНИЕ
    # --------------------------------------------------------

    report = (
        "🔎 АНАЛИЗ ТВОИХ ДАННЫХ\n\n"

        "Что я делаю:\n"
        "Я ищу закономерности между твоими привычками "
        "(сон, кофеин, экран, активность) и самочувствием "
        "(настроение, энергия, стресс).\n\n"

        "Как читать результат:\n"
        "• «Прямая связь» — когда одно растёт, второе тоже растёт.\n"
        "• «Обратная связь» — когда одно растёт, второе снижается.\n"
        "• Чем сильнее связь, тем чаще она подтверждается в твоих данных.\n\n"

        "⚠️ Важно: это наблюдаемые закономерности, "
        "а не доказательство причины и следствия.\n"
    )

    # --------------------------------------------------------
    # СРЕДНИЕ ПОКАЗАТЕЛИ
    # --------------------------------------------------------

    report += "\n📊 СРЕДНИЕ ПОКАЗАТЕЛИ\n\n"

    if average(sleep_values) is not None:
        report += f"😴 Сон: {average(sleep_values):.1f} ч\n"

    if average(quality_values) is not None:
        report += f"⭐ Качество: {average(quality_values):.1f}/5\n"

    if average(mood_values) is not None:
        report += f"🙂 Настроение: {average(mood_values):.1f}/5\n"

    if average(energy_values) is not None:
        report += f"⚡ Энергия: {average(energy_values):.1f}/5\n"

    if stress_values and average(stress_values) is not None:
        report += f"😰 Стресс: {average(stress_values):.1f}/5\n"

    # --------------------------------------------------------
    # СВЯЗИ
    # --------------------------------------------------------

    pairs = [
        (
            correlation(sleep_values, energy_values),
            "😴→⚡ Чем больше ты спишь, тем выше твоя энергия.",
            "😴→⚡ Чем больше ты спишь, тем ниже твоя энергия.",
        ),
        (
            correlation(sleep_values, mood_values),
            "😴→🙂 Чем больше ты спишь, тем лучше настроение.",
            "😴→🙂 Чем больше ты спишь, тем хуже настроение.",
        ),
        (
            correlation(sleep_values, quality_values),
            "😴→⭐ Чем дольше сон, тем выше его качество.",
            "😴→⭐ Чем дольше сон, тем ниже его качество.",
        ),
        (
            correlation(sleep_values, stress_values),
            "😴→😰 Чем больше ты спишь, тем выше стресс.",
            "😴→😰 Чем больше ты спишь, тем ниже стресс.",
        ),
        (
            correlation(quality_values, energy_values),
            "⭐→⚡ Чем выше качество сна, тем больше энергии.",
            "⭐→⚡ Чем выше качество сна, тем меньше энергии.",
        ),
        (
            correlation(quality_values, mood_values),
            "⭐→🙂 Чем выше качество сна, тем лучше настроение.",
            "⭐→🙂 Чем выше качество сна, тем хуже настроение.",
        ),
        (
            correlation(quality_values, stress_values),
            "⭐→😰 Чем выше качество сна, тем выше стресс.",
            "⭐→😰 Чем выше качество сна, тем ниже стресс.",
        ),
        (
            correlation(stress_values, mood_values),
            "😰→🙂 Чем выше стресс, тем лучше настроение.",
            "😰→🙂 Чем выше стресс, тем хуже настроение.",
        ),
        (
            correlation(stress_values, energy_values),
            "😰→⚡ Чем выше стресс, тем больше энергии.",
            "😰→⚡ Чем выше стресс, тем меньше энергии.",
        ),
        (
            correlation(caffeine_values, sleep_values),
            "☕→😴 Чем больше кофеина, тем дольше сон.",
            "☕→😴 Чем больше кофеина, тем короче сон.",
        ),
        (
            correlation(caffeine_values, quality_values),
            "☕→⭐ Чем больше кофеина, тем выше качество сна.",
            "☕→⭐ Чем больше кофеина, тем ниже качество сна.",
        ),
        (
            correlation(screen_values, sleep_values),
            "📱→😴 Чем больше экрана, тем дольше сон.",
            "📱→😴 Чем больше экрана, тем короче сон.",
        ),
        (
            correlation(screen_values, quality_values),
            "📱→⭐ Чем больше экрана, тем выше качество сна.",
            "📱→⭐ Чем больше экрана, тем ниже качество сна.",
        ),
        (
            correlation(screen_values, energy_values),
            "📱→⚡ Чем больше экрана, тем больше энергии.",
            "📱→⚡ Чем больше экрана, тем меньше энергии.",
        ),
        (
            correlation(activity_values, energy_values),
            "🏃→⚡ Чем выше активность, тем больше энергии.",
            "🏃→⚡ Чем выше активность, тем меньше энергии.",
        ),
        (
            correlation(activity_values, quality_values),
            "🏃→⭐ Чем выше активность, тем выше качество сна.",
            "🏃→⭐ Чем выше активность, тем ниже качество сна.",
        ),
        (
            correlation(nap_values, sleep_values),
            "🌙→😴 Чем дольше дневной сон, тем дольше основной.",
            "🌙→😴 Чем дольше дневной сон, тем короче основной.",
        ),
        (
            correlation(nap_values, energy_values),
            "🌙→⚡ Чем дольше дневной сон, тем больше энергии.",
            "🌙→⚡ Чем дольше дневной сон, тем меньше энергии.",
        ),
    ]

    # Связь времени кофеина
    valid_caffeine = [
        v for v in caffeine_before_sleep_values if v is not None
    ]

    if len(valid_caffeine) >= 5:
        r = correlation(
            caffeine_before_sleep_values,
            quality_values
        )
        pairs.append((
            r,
            "⏰→⭐ Чем больше времени между кофеином и сном, тем выше качество сна.",
            "⏰→⭐ Чем ближе кофеин ко сну, тем выше качество сна.",
        ))

        r = correlation(
            caffeine_before_sleep_values,
            sleep_values
        )
        pairs.append((
            r,
            "⏰→😴 Чем раньше был кофеин, тем продолжительнее сон.",
            "⏰→😴 Чем раньше был кофеин, тем короче сон.",
        ))

    # --------------------------------------------------------
    # СОРТИРУЕМ СВЯЗИ ПО СИЛЕ
    # --------------------------------------------------------

    observations = []

    for r, positive_text, negative_text in pairs:
        result = plain_language(r, positive_text, negative_text)

        if result:
            observations.append((abs(r), result))

    observations.sort(key=lambda x: x[0], reverse=True)

    report += "\n🔗 НАБЛЮДАЕМЫЕ СВЯЗИ\n\n"

    if observations:
        # Показываем только связи с r >= 0.3
        for _, text in observations[:7]:
            report += f"• {text}\n\n"
    else:
        report += (
            "• Пока выраженных связей не обнаружено.\n"
            "Продолжай заполнять чек-ины — "
            "закономерности появятся по мере накопления данных.\n"
        )

    report += (
        "\n📌 ИТОГ\n\n"
        "Это наблюдаемые закономерности в твоих данных, "
        "а не диагноз и не доказательство причины. "
        "Чем больше дней ты заполняешь, тем точнее "
        "становится анализ."
    )

    await message.answer(report)