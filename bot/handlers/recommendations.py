from aiogram import F, Router
from aiogram.types import Message

from bot.database.db import (
    get_user,
    get_user_statistics,
    get_checkins_for_analysis,
)

from bot.logic.sleep_model import (
    build_sleep_profile,
    build_best_conditions,
    format_sleep_profile,
    format_best_conditions,
    nap_to_number,
    caffeine_to_number,
    screen_to_number,
    activity_to_number,
    caffeine_hours_before_sleep,
)


router = Router()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def calculate_correlation(x_values, y_values):
    """
    Расчёт коэффициента корреляции Пирсона.
    Используется только если есть минимум 5 пар наблюдений.
    """

    pairs = []

    for x, y in zip(x_values, y_values):
        if x is None or y is None:
            continue

        try:
            pairs.append((float(x), float(y)))
        except (TypeError, ValueError):
            continue

    if len(pairs) < 5:
        return None

    x = [pair[0] for pair in pairs]
    y = [pair[1] for pair in pairs]

    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)

    numerator = sum(
        (xi - mean_x) * (yi - mean_y)
        for xi, yi in zip(x, y)
    )

    denominator_x = sum(
        (xi - mean_x) ** 2
        for xi in x
    )

    denominator_y = sum(
        (yi - mean_y) ** 2
        for yi in y
    )

    denominator = (denominator_x * denominator_y) ** 0.5

    if denominator == 0:
        return None

    return numerator / denominator


def correlation_text(r, positive_text, negative_text):
    """
    Превращает коэффициент корреляции в понятный текст.
    """

    if r is None:
        return None

    if abs(r) < 0.2:
        return None

    if r >= 0.2:
        return f"{positive_text} (r={r:.2f})"

    if r <= -0.2:
        return f"{negative_text} (r={r:.2f})"

    return None


# ============================================================
# ОСНОВНОЙ ОБРАБОТЧИК
# ============================================================

@router.message(F.text == "💡 Рекомендации")
async def recommendations_handler(message: Message):

    user = get_user(message.from_user.id)

    if not user:
        await message.answer(
            "Сначала пройди регистрацию через /start."
        )
        return

    # get_user возвращает кортеж:
    # (telegram_id, name, age, category, schedule)
    telegram_id, name, age, category, schedule = user

    category = category or ""
    schedule = schedule or ""

    # --------------------------------------------------------
    # ПОЛУЧАЕМ ДАННЫЕ
    # --------------------------------------------------------

    (
        days_stat,
        avg_sleep,
        avg_quality,
        avg_mood,
        avg_energy,
        nap_days,
        avg_stress,
    ) = get_user_statistics(telegram_id)

    rows = get_checkins_for_analysis(telegram_id)

    if not rows:
        await message.answer(
            "Пока у меня нет данных для рекомендаций 😴\n\n"
            "Сначала отметь хотя бы один день сна."
        )
        return

    # --------------------------------------------------------
    # ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ СНА
    # --------------------------------------------------------

    sleep_profile = build_sleep_profile(
        rows,
        age,
        schedule
    )

    best_conditions = build_best_conditions(rows)

    recommendations = []

    # --------------------------------------------------------
    # ОБЩАЯ ИНФОРМАЦИЯ
    # --------------------------------------------------------

    days = len(rows)

    recommendations.append(
        f"📊 Сейчас у меня есть данные за {days} "
        f"{'день' if days == 1 else 'дней'}."
    )

    # --------------------------------------------------------
    # ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ
    # --------------------------------------------------------

    profile_text = format_sleep_profile(sleep_profile)

    if profile_text:
        recommendations.append(profile_text)

    best_conditions_text = format_best_conditions(best_conditions)

    if best_conditions_text:
        recommendations.append(best_conditions_text)

    # --------------------------------------------------------
    # СОН
    # --------------------------------------------------------

    if avg_sleep is not None:

        target_sleep = sleep_profile.get("personal_target")

        if target_sleep is not None:

            difference = avg_sleep - target_sleep

            if difference <= -1:
                recommendations.append(
                    f"😴 В среднем ты спишь {avg_sleep:.1f} ч, "
                    f"а твой текущий ориентир — около "
                    f"{target_sleep:.1f} ч. "
                    "Попробуй постепенно увеличить время сна."
                )

            elif difference >= 1:
                recommendations.append(
                    f"😴 В среднем получается {avg_sleep:.1f} ч сна. "
                    f"Это примерно на {difference:.1f} ч больше "
                    f"твоего текущего ориентира."
                )

            else:
                recommendations.append(
                    f"😴 Средняя продолжительность сна — "
                    f"{avg_sleep:.1f} ч. "
                    "Она близка к твоему текущему ориентиру."
                )

    # --------------------------------------------------------
    # КАЧЕСТВО СНА
    # --------------------------------------------------------

    if avg_quality is not None:

        if avg_quality < 3:
            recommendations.append(
                "⭐ Средняя оценка качества сна ниже 3/5. "
                "Стоит обратить внимание на стабильность режима, "
                "условия перед сном и факторы, которые могут "
                "мешать восстановлению."
            )

        elif avg_quality < 4:
            recommendations.append(
                "⭐ Качество сна в среднем умеренное. "
                "Посмотри, какие условия чаще совпадают "
                "с твоими лучшими днями."
            )

        else:
            recommendations.append(
                "⭐ Ты в среднем оцениваешь качество сна "
                "как хорошее."
            )

    # --------------------------------------------------------
    # СТРЕСС
    # --------------------------------------------------------

    if avg_stress is not None:

        if avg_stress >= 4:
            recommendations.append(
                "😰 Средний уровень стресса довольно высокий. "
                "Обрати внимание на связь стресса с качеством сна, "
                "настроением и энергией."
            )

        elif avg_stress >= 3:
            recommendations.append(
                "😰 Уровень стресса в среднем умеренный. "
                "Полезно наблюдать, как он меняется вместе "
                "со сном и самочувствием."
            )

    # --------------------------------------------------------
    # ЭНЕРГИЯ
    # --------------------------------------------------------

    if avg_energy is not None:

        if avg_energy < 3:
            recommendations.append(
                "⚡ Средняя энергия ниже 3/5. "
                "Проверь, достаточно ли тебе сна и "
                "насколько стабилен режим."
            )

        elif avg_energy >= 4:
            recommendations.append(
                "⚡ Уровень энергии в среднем хороший."
            )

    # ========================================================
    # КОРРЕЛЯЦИИ
    # ========================================================

    sleep_values = []
    quality_values = []
    mood_values = []
    energy_values = []
    stress_values = []
    caffeine_values = []
    caffeine_timing_values = []
    screen_values = []
    activity_values = []
    nap_values = []

    for row in rows:

        sleep = row[0]
        quality = row[1]
        mood = row[2]
        energy = row[3]
        stress = row[4]
        caffeine = row[5]
        caffeine_time = row[6]
        screen = row[7]
        activity = row[8]
        nap_taken = row[9]
        nap_duration = row[10]
        sleep_time = row[11]

        if sleep is not None:
            sleep_values.append(float(sleep))

        if quality is not None:
            quality_values.append(float(quality))

        if mood is not None:
            mood_values.append(float(mood))

        if energy is not None:
            energy_values.append(float(energy))

        if stress is not None:
            stress_values.append(float(stress))

        caffeine_values.append(
            caffeine_to_number(caffeine)
        )

        screen_values.append(
            screen_to_number(screen)
        )

        activity_values.append(
            activity_to_number(activity)
        )

        if nap_taken:
            nap_values.append(
                nap_to_number(nap_duration)
            )
        else:
            nap_values.append(0)

        caffeine_timing_values.append(
            caffeine_hours_before_sleep(
                caffeine_time,
                sleep_time
            )
        )

    # --------------------------------------------------------
    # СОН ↔ ЭНЕРГИЯ
    # --------------------------------------------------------

    r = calculate_correlation(
        sleep_values,
        energy_values
    )

    text = correlation_text(
        r,
        "📈 В твоих данных больше сна связано с более высокой энергией",
        "📉 В твоих данных больше сна связано с более низкой энергией"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # СОН ↔ НАСТРОЕНИЕ
    # --------------------------------------------------------

    r = calculate_correlation(
        sleep_values,
        mood_values
    )

    text = correlation_text(
        r,
        "🙂 Более продолжительный сон связан с более высоким настроением",
        "🙂 Более продолжительный сон связан с более низким настроением"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # КАЧЕСТВО ↔ ЭНЕРГИЯ
    # --------------------------------------------------------

    r = calculate_correlation(
        quality_values,
        energy_values
    )

    text = correlation_text(
        r,
        "⭐ Лучшее качество сна связано с более высокой энергией",
        "⭐ Более высокое качество сна связано с более низкой энергией"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # СТРЕСС ↔ НАСТРОЕНИЕ
    # --------------------------------------------------------

    r = calculate_correlation(
        stress_values,
        mood_values
    )

    text = correlation_text(
        r,
        "😰 Более высокий стресс связан с более высоким настроением",
        "😰 Более высокий стресс связан с более низким настроением"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # СТРЕСС ↔ ЭНЕРГИЯ
    # --------------------------------------------------------

    r = calculate_correlation(
        stress_values,
        energy_values
    )

    text = correlation_text(
        r,
        "😰 Более высокий стресс связан с большей энергией",
        "😰 Более высокий стресс связан с меньшей энергией"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # КОФЕИН ↔ СОН
    # --------------------------------------------------------

    r = calculate_correlation(
        caffeine_values,
        sleep_values
    )

    text = correlation_text(
        r,
        "☕ В твоих данных больше кофеина связано с более продолжительным сном",
        "☕ В твоих данных больше кофеина связано с более коротким сном"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # КОФЕИН ↔ КАЧЕСТВО
    # --------------------------------------------------------

    r = calculate_correlation(
        caffeine_values,
        quality_values
    )

    text = correlation_text(
        r,
        "☕ Большее количество кофеина связано с более высоким качеством сна",
        "☕ Большее количество кофеина связано с более низким качеством сна"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # ВРЕМЯ КОФЕИНА ↔ КАЧЕСТВО
    # --------------------------------------------------------

    r = calculate_correlation(
        caffeine_timing_values,
        quality_values
    )

    text = correlation_text(
        r,
        "☕ Чем раньше относительно сна был кофеин, тем выше качество сна",
        "☕ Более позднее употребление кофеина связано с более низким качеством сна"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # ЭКРАН ↔ СОН
    # --------------------------------------------------------

    r = calculate_correlation(
        screen_values,
        sleep_values
    )

    text = correlation_text(
        r,
        "📱 Большее экранное время связано с более продолжительным сном",
        "📱 Большее экранное время связано с более коротким сном"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # ЭКРАН ↔ КАЧЕСТВО
    # --------------------------------------------------------

    r = calculate_correlation(
        screen_values,
        quality_values
    )

    text = correlation_text(
        r,
        "📱 Большее экранное время связано с более высоким качеством сна",
        "📱 Большее экранное время связано с более низким качеством сна"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # ЭКРАН ↔ ЭНЕРГИЯ
    # --------------------------------------------------------

    r = calculate_correlation(
        screen_values,
        energy_values
    )

    text = correlation_text(
        r,
        "📱 Большее экранное время связано с большей энергией",
        "📱 Большее экранное время связано с меньшей энергией"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # ДНЕВНОЙ СОН ↔ ОСНОВНОЙ СОН
    # --------------------------------------------------------

    r = calculate_correlation(
        nap_values,
        sleep_values
    )

    text = correlation_text(
        r,
        "😴 Более длительный дневной сон связан с более продолжительным основным сном",
        "😴 Более длительный дневной сон связан с более коротким основным сном"
    )

    if text:
        recommendations.append(text)

    # --------------------------------------------------------
    # АКТИВНОСТЬ ↔ ЭНЕРГИЯ
    # --------------------------------------------------------

    r = calculate_correlation(
        activity_values,
        energy_values
    )

    text = correlation_text(
        r,
        "🏃 Более высокая физическая активность связана с большей энергией",
        "🏃 Более высокая физическая активность связана с меньшей энергией"
    )

    if text:
        recommendations.append(text)

    # ========================================================
    # АДАПТАЦИЯ ПО КАТЕГОРИИ
    # ========================================================

    if "Офисный" in category or "умственный" in category:

        recommendations.append(
            "🧑‍💻 При умственной работе особенно полезно "
            "следить за стабильностью сна и уровнем энергии "
            "в течение дня."
        )

        recommendations.append(
            "🧑‍💻 Если замечаешь снижение энергии после "
            "плохого сна, ориентируйся не только на "
            "продолжительность сна, но и на его качество."
        )

    elif "Сменный" in category or "ночной" in category.lower():

        total_sleep_values = []

        for row in rows:

            sleep = row[0]
            nap_taken = row[9]
            nap_duration = row[10]

            if sleep is None:
                continue

            total_sleep = float(sleep)

            if nap_taken:
                total_sleep += nap_to_number(
                    nap_duration
                )

            total_sleep_values.append(total_sleep)

        if total_sleep_values:

            avg_total_sleep = (
                sum(total_sleep_values)
                / len(total_sleep_values)
            )

            recommendations.append(
                "🔄 При сменном графике «Подушка» "
                "учитывает не только основной сон, "
                "но и дневной сон как часть восстановления "
                "за сутки.\n\n"
                f"📊 В среднем сейчас получается около "
                f"{avg_total_sleep:.1f} ч сна за сутки."
            )

        recommendations.append(
            "🌙 При сменном графике старайся оценивать "
            "не отдельную ночь, а восстановление за сутки: "
            "основной сон + дневной сон + энергия + настроение."
        )

    elif "Физический" in category:

        recommendations.append(
            "🏃 При высокой физической нагрузке особенно "
            "важно следить за достаточной продолжительностью "
            "сна и восстановлением."
        )

        recommendations.append(
            "🏃 Сравнивай дни с разной физической нагрузкой "
            "и смотри, как она связана с твоей энергией "
            "и качеством сна."
        )

    elif "Свободный" in category or "фриланс" in category.lower():

        recommendations.append(
            "🎨 При свободном графике особенно полезно "
            "сохранять относительно стабильное время сна "
            "и пробуждения."
        )

        recommendations.append(
            "🎨 Используй свои лучшие дни как ориентир: "
            "«Подушка» постепенно определяет условия, "
            "при которых ты восстанавливаешься лучше."
        )

    elif "Учебный" in category:

        recommendations.append(
            "📚 При учебной нагрузке обрати внимание "
            "на связь продолжительности сна с энергией "
            "и настроением."
        )

        recommendations.append(
            "📚 Старайся не компенсировать регулярный "
            "недосып только отдельными длинными снами."
        )

    # ========================================================
    # АДАПТАЦИЯ ПО ГРАФИКУ
    # ========================================================

    if "Ночной" in schedule:

        recommendations.append(
            "🌙 При ночном графике особенно важно "
            "оценивать восстановление за сутки, "
            "а не только продолжительность одного периода сна."
        )

    elif "Сменный" in schedule:

        recommendations.append(
            "🔄 При сменном графике режим может меняться, "
            "поэтому «Подушка» будет полезнее по мере накопления "
            "данных за разные дни."
        )

    elif "Дневной" in schedule:

        recommendations.append(
            "☀️ При дневном графике старайся сохранять "
            "примерно одинаковое время сна и пробуждения."
        )

    elif "Свободный" in schedule:

        recommendations.append(
            "🕐 При свободном графике ориентируйся "
            "на собственные данные и повторяющиеся условия "
            "лучших дней."
        )

    # ========================================================
    # УРОВЕНЬ ДОСТОВЕРНОСТИ
    # ========================================================

    if days < 5:

        recommendations.append(
            "📌 Пока данных мало. Сделай ещё несколько "
            "чек-инов — тогда рекомендации станут "
            "более персональными."
        )

    elif days < 7:

        recommendations.append(
            "📌 Уже начинает формироваться твой личный "
            "профиль сна. Продолжай отмечать сон ежедневно."
        )

    elif days < 14:

        recommendations.append(
            "📌 Данных уже достаточно для первых наблюдений. "
            "Чем дольше ты ведёшь дневник, тем точнее "
            "становятся персональные рекомендации."
        )

    elif days < 28:

        recommendations.append(
            "📌 У тебя уже накоплена хорошая база наблюдений. "
            "Продолжай — после 28 дней можно увереннее "
            "оценивать твои индивидуальные закономерности."
        )

    else:

        recommendations.append(
            "📌 У тебя накоплено 28+ дней наблюдений. "
            "Теперь персональные закономерности можно "
            "оценивать значительно увереннее."
        )

    # ========================================================
    # УДАЛЯЕМ ДУБЛИКАТЫ
    # ========================================================

    unique_recommendations = []

    for recommendation in recommendations:

        if not recommendation:
            continue

        if recommendation not in unique_recommendations:
            unique_recommendations.append(
                recommendation
            )

    # Не перегружаем Telegram-сообщение
    unique_recommendations = unique_recommendations[:8]

    # ========================================================
    # ФОРМИРУЕМ ОТВЕТ
    # ========================================================

    text = "💡 Твои персональные рекомендации\n\n"

    for recommendation in unique_recommendations:
        text += recommendation + "\n\n"

    text += (
        "⚠️ Эти рекомендации основаны на твоих "
        "наблюдениях за сном и самочувствием и "
        "не заменяют медицинскую консультацию."
    )

    await message.answer(text)