from aiogram import F, Router
from aiogram.types import Message

from bot.database.db import (
    get_user,
    get_user_statistics,
    get_checkins_for_analysis,
)

from bot.logic.sleep_model import (
    build_sleep_profile,
)


router = Router()


@router.message(F.text == "📊 Моя статистика")
async def show_statistics(message: Message):

    telegram_id = message.from_user.id

    user = get_user(telegram_id)

    if not user:
        await message.answer(
            "Сначала пройди регистрацию через /start."
        )
        return

    _, name, age, category, schedule = user

    statistics = get_user_statistics(telegram_id)

    (
        days,
        avg_sleep,
        avg_quality,
        avg_mood,
        avg_energy,
        nap_days,
        avg_stress,
    ) = statistics

    if days == 0:
        await message.answer(
            "📊 Пока статистики нет.\n\n"
            "Сначала заполни хотя бы один чек-ин 😴"
        )
        return

    text = (
        "📊 ТВОЯ СТАТИСТИКА\n\n"
        f"👤 {name}\n"
        f"📅 Заполнено дней: {days}\n\n"
    )

    if avg_sleep is not None:
        text += (
            f"😴 Средняя продолжительность сна: "
            f"{avg_sleep:.1f} ч\n"
        )

    if avg_quality is not None:
        text += (
            f"⭐ Среднее качество сна: "
            f"{avg_quality:.1f}/5\n"
        )

    if avg_mood is not None:
        text += (
            f"🙂 Среднее настроение: "
            f"{avg_mood:.1f}/5\n"
        )

    if avg_energy is not None:
        text += (
            f"⚡ Средняя энергия: "
            f"{avg_energy:.1f}/5\n"
        )

    if avg_stress is not None:
        text += (
            f"😰 Средний стресс: "
            f"{avg_stress:.1f}/5\n"
        )

    text += (
        f"🌙 Дней с дневным сном: "
        f"{nap_days}\n"
    )

    # -----------------------------------------------------
    # ОЦЕНКА СРЕДНЕГО СНА
    # -----------------------------------------------------

    if avg_sleep is not None:
        if avg_sleep < 6:
            text += (
                "\n⚠️ Средняя продолжительность сна "
                "довольно низкая."
            )

        elif avg_sleep < 7:
            text += (
                "\n💡 Можно попробовать увеличить "
                "продолжительность сна."
            )

        elif avg_sleep < 7.5:
            text += (
                "\n💡 Сон находится около нижней границы "
                "возрастного ориентира."
            )

        else:
            text += (
                "\n✅ Средняя продолжительность сна "
                "выглядит достаточно стабильной."
            )

    if avg_quality is not None and avg_quality < 3:
        text += (
            "\n⭐ Средняя оценка качества сна низкая."
        )

    if avg_stress is not None and avg_stress >= 4:
        text += (
            "\n😰 Средний уровень стресса высокий."
        )

    if avg_energy is not None and avg_energy <= 2:
        text += (
            "\n⚡ Средняя дневная энергия низкая."
        )

    # -----------------------------------------------------
    # ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ
    # -----------------------------------------------------

    rows = get_checkins_for_analysis(telegram_id)

    sleep_profile = build_sleep_profile(
        rows,
        age
    )

    text += "\n\n🎯 ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ СНА\n\n"

    if sleep_profile["mode"] == "baseline":

        text += (
            "Пока мы используем возрастной ориентир.\n"
            f"Стартовая точка: "
            f"около {sleep_profile['baseline_target']:.1f} ч.\n\n"
            f"Для персонального анализа нужно накопить "
            f"больше данных. Сейчас: {days} дней."
        )

    elif sleep_profile["mode"] == "preliminary":

        text += (
            "Мы уже начали искать твой индивидуальный "
            "оптимальный диапазон.\n\n"
            f"Лучшие наблюдаемые результаты были примерно "
            f"при {sleep_profile['best_observed']:.1f} ч сна.\n"
            f"Текущий ориентир: "
            f"{sleep_profile['personal_target']:.1f} ч.\n\n"
            "Профиль пока предварительный и будет уточняться."
        )

    elif sleep_profile["mode"] == "personal":

        text += (
            "Модель уже нашла устойчивый личный паттерн.\n\n"
            f"🎯 Лучшие наблюдаемые результаты: "
            f"{sleep_profile['best_observed']:.1f} ч\n"
            f"🛌 Рабочая зона: "
            f"{sleep_profile['zone_low']:.1f}–"
            f"{sleep_profile['zone_high']:.1f} ч\n"
            f"📌 Персональный ориентир: "
            f"{sleep_profile['personal_target']:.1f} ч\n"
            f"📊 Дней наблюдения: "
            f"{sleep_profile['days']}\n"
            f"🔎 Достоверность паттерна: "
            f"{sleep_profile['confidence']}."
        )

    else:

        text += (
            "Персональные данные уже накоплены, "
            "но выраженного устойчивого паттерна "
            "пока недостаточно.\n\n"
            f"Текущий ориентир: "
            f"{sleep_profile['personal_target']:.1f} ч."
        )

    await message.answer(text)