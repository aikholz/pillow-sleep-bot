from datetime import date, timedelta

from aiogram import F, Router
from aiogram.types import Message

from bot.database.db import (
    get_user,
    get_first_checkin_date,
    get_checkins_for_period,
)

from bot.logic.sleep_model import (
    build_sleep_profile,
)


router = Router()


@router.message(F.text == "📈 Первый отчёт")
async def show_first_report(message: Message):

    telegram_id = message.from_user.id

    user = get_user(telegram_id)

    if not user:
        await message.answer(
            "Сначала пройди регистрацию через /start."
        )
        return

    _, name, age, category, schedule = user

    first_date_str = get_first_checkin_date(telegram_id)

    if not first_date_str:
        await message.answer(
            "📈 Для первого отчёта пока нет данных.\n\n"
            "Сначала заполни чек-ин 😴"
        )
        return

    first_date = date.fromisoformat(first_date_str)

    report_end = first_date + timedelta(days=6)

    rows = get_checkins_for_period(
        telegram_id,
        str(first_date),
        str(report_end),
    )

    days = len(rows)

    if days < 5:

        await message.answer(
            "📈 ПЕРВЫЙ ОТЧЁТ\n\n"
            f"За первые 7 дней заполнено: {days} из 7.\n\n"
            "Для формирования первого отчёта нужно "
            "минимум 5 заполненных дней.\n\n"
            "Продолжай заполнять ежедневный чек-ин 😴"
        )
        return

    # -----------------------------------------------------
    # МЕТРИКИ НЕДЕЛИ
    # -----------------------------------------------------

    sleep_values = [
        row[1] for row in rows if row[1] is not None
    ]

    quality_values = [
        row[2] for row in rows if row[2] is not None
    ]

    mood_values = [
        row[3] for row in rows if row[3] is not None
    ]

    energy_values = [
        row[4] for row in rows if row[4] is not None
    ]

    nap_days = sum(
        row[5] for row in rows if row[5] is not None
    )

    stress_values = [
        row[10] for row in rows if row[10] is not None
    ]

    avg_sleep = (
        sum(sleep_values) / len(sleep_values)
        if sleep_values
        else 0
    )

    avg_quality = (
        sum(quality_values) / len(quality_values)
        if quality_values
        else 0
    )

    avg_mood = (
        sum(mood_values) / len(mood_values)
        if mood_values
        else 0
    )

    avg_energy = (
        sum(energy_values) / len(energy_values)
        if energy_values
        else 0
    )

    avg_stress = (
        sum(stress_values) / len(stress_values)
        if stress_values
        else None
    )

    # -----------------------------------------------------
    # ОТЧЁТ
    # -----------------------------------------------------

    report = (
        "📈 ПЕРВЫЙ ОТЧЁТ «ПОДУШКИ»\n\n"
        f"👤 {name}\n"
        f"📅 Период: {first_date.strftime('%d.%m.%Y')} — "
        f"{report_end.strftime('%d.%m.%Y')}\n"
        f"✅ Заполнено дней: {days}/7\n\n"
    )

    report += (
        "📊 ОСНОВНЫЕ ПОКАЗАТЕЛИ\n\n"
        f"😴 Средний сон: {avg_sleep:.1f} ч\n"
        f"⭐ Качество сна: {avg_quality:.1f}/5\n"
        f"🙂 Настроение: {avg_mood:.1f}/5\n"
        f"⚡ Энергия: {avg_energy:.1f}/5\n"
    )

    if avg_stress is not None:
        report += (
            f"😰 Стресс: {avg_stress:.1f}/5\n"
        )

    report += (
        f"🌙 Дневной сон: {nap_days} дн.\n\n"
    )

    # -----------------------------------------------------
    # ВЫВОДЫ
    # -----------------------------------------------------

    report += "🔎 ОСНОВНЫЕ ВЫВОДЫ\n\n"

    observations = []

    if avg_sleep < 7:
        observations.append(
            "😴 Средняя продолжительность сна "
            "получилась ниже возрастного ориентира."
        )

    elif avg_sleep < 7.5:
        observations.append(
            "😴 Средняя продолжительность сна "
            "находится около нижней границы ориентира."
        )

    else:
        observations.append(
            "😴 Средняя продолжительность сна "
            "выглядит достаточно стабильной."
        )

    if avg_quality >= 4:
        observations.append(
            "⭐ Ты в среднем высоко оцениваешь качество сна."
        )

    elif avg_quality < 3:
        observations.append(
            "⭐ Средняя оценка качества сна довольно низкая."
        )

    if avg_energy >= 4:
        observations.append(
            "⚡ Дневная энергия в среднем высокая."
        )

    elif avg_energy <= 2:
        observations.append(
            "⚡ Дневная энергия в среднем низкая."
        )

    if avg_stress is not None:

        if avg_stress >= 4:
            observations.append(
                "😰 Средний уровень стресса высокий."
            )

        elif avg_stress <= 2:
            observations.append(
                "😌 Средний уровень стресса невысокий."
            )

    report += "\n".join(
        f"• {item}"
        for item in observations
    )

    # -----------------------------------------------------
    # АДАПТАЦИЯ ПО КАТЕГОРИИ
    # -----------------------------------------------------

    report += "\n\n🧩 С УЧЁТОМ ТВОЕЙ КАТЕГОРИИ\n\n"

    if "Офисный" in category:
        report += (
            "🧑‍💻 При умственной работе особенно важно "
            "не использовать сон как резерв времени "
            "для рабочих задач."
        )

    elif "Сменный" in category:
        report += (
            "🌙 При сменном графике режим может сильно "
            "отличаться от обычного дневного режима. "
            "Поэтому для тебя особенно важна оценка "
            "восстановления относительно типа смены."
        )

    elif "Физический" in category:
        report += (
            "🏃 При физической нагрузке сон играет важную "
            "роль в восстановлении, поэтому будем отдельно "
            "сравнивать его с дневной энергией."
        )

    elif "Свободный" in category:
        report += (
            "🎨 При свободном графике особенно полезно "
            "наблюдать стабильность времени сна и подъёма."
        )

    elif "Учебный" in category:
        report += (
            "📚 Для учебного графика важно наблюдать, "
            "как сон связан с энергией и настроением "
            "в учебные дни."
        )

    # -----------------------------------------------------
    # ПЕРСОНАЛЬНАЯ МОДЕЛЬ
    # -----------------------------------------------------

    model_rows = [
        (
            row[1],   # sleep_duration
            row[2],   # sleep_quality
            row[3],   # mood
            row[4],   # energy
            row[10],  # stress
        )
        for row in rows
    ]

    all_first_week_profile = build_sleep_profile(
        model_rows,
        age
    )

    report += "\n\n🎯 ПЕРСОНАЛИЗАЦИЯ\n\n"

    if all_first_week_profile["mode"] == "baseline":

        report += (
            "Это первая неделя наблюдения, поэтому "
            "пока используем возрастной ориентир.\n"
            "Продолжай заполнять чек-ины — со временем "
            "«Подушка» начнёт искать именно твой "
            "индивидуальный диапазон сна."
        )

    else:

        report += (
            f"Лучшие наблюдаемые результаты в накопленных "
            f"данных были около "
            f"{all_first_week_profile['best_observed']:.1f} ч."
        )

    # -----------------------------------------------------
    # ИТОГ
    # -----------------------------------------------------

    report += (
        "\n\n💡 ИТОГ\n\n"
        "Первый отчёт — это отправная точка. "
        "Чем регулярнее ты заполняешь чек-ин, тем "
        "точнее «Подушка» сможет определить твои "
        "личные закономерности сна.\n\n"
        "⚠️ Отчёт показывает наблюдаемые закономерности "
        "и не является медицинским диагнозом."
    )

    await message.answer(report)