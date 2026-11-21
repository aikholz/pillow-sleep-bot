from datetime import date, timedelta
import os

from aiogram import F, Router
from aiogram.types import FSInputFile, Message

from bot.database.db import (
    get_user,
    get_checkins_for_period,
    get_checkins_for_analysis,
)
from bot.logic.charts import (
    make_sleep_by_day_chart,
    make_study_load_chart,
    make_study_time_chart,
    make_circadian_chart,
    make_progress_chart,
    make_shift_chart,
)
from bot.logic.sleep_model import (
    analyze_circadian,
    build_circadian_insights,
)

router = Router()


@router.message(F.text == "📈 Мой прогресс")
async def show_charts(message: Message):
    user = get_user(message.from_user.id)

    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    telegram_id, name, age, category, schedule = user

    period_start = date.today() - timedelta(days=30)
    period_end = date.today()

    period_rows = get_checkins_for_period(
        telegram_id,
        str(period_start),
        str(period_end),
    )

    if len(period_rows) < 3:
        await message.answer(
            "📈 Пока мало данных для графиков.\n\n"
            f"Заполнено дней: {len(period_rows)}\n"
            "Нужно минимум 3."
        )
        return

    # ГРАФИК 1: Сон по дням
    path1 = make_sleep_by_day_chart(period_rows)
    if path1:
        await message.answer_photo(
            FSInputFile(path1, filename="sleep_by_day.png"),
            caption="📈 <b>Сон по дням</b>\n\nКрасная линия — твоё среднее.",
            parse_mode="HTML",
        )
        os.remove(path1)

    all_rows = get_checkins_for_analysis(telegram_id)

    # ГРАФИК 2 и 4: Учебная нагрузка и Время учебы
    if "Учебный" in category or "Учебный" in schedule:
        path2 = make_study_load_chart(all_rows)
        if path2:
            await message.answer_photo(
                FSInputFile(path2, filename="study_load.png"),
                caption=(
                    "📚 <b>Влияние учебной нагрузки на сон</b>\n\n"
                    "Столбцы показывают средний сон в дни с высокой нагрузкой и в обычные дни."
                ),
                parse_mode="HTML",
            )
            os.remove(path2)

        path4 = make_study_time_chart(all_rows)
        if path4:
            await message.answer_photo(
                FSInputFile(path4, filename="study_time.png"),
                caption=(
                    "📚 <b>Сон и время учебы</b>\n\n"
                    "Столбцы показывают, как время учебы влияет на твой сон."
                ),
                parse_mode="HTML",
            )
            os.remove(path4)

    # ГРАФИК 3: Циркадный ритм
    circ = analyze_circadian(period_rows)
    if circ:
        path3 = make_circadian_chart(circ)
        if path3:
            circ_text = build_circadian_insights(circ) or ""
            await message.answer_photo(
                FSInputFile(path3, filename="circadian.png"),
                caption=f"🕐 <b>Циркадный ритм</b>\n\n{circ_text}",
                parse_mode="HTML",
            )
            os.remove(path3)

    # ГРАФИК 5: Динамика прогресса
    path_progress = make_progress_chart(period_rows)
    if path_progress:
        await message.answer_photo(
            FSInputFile(path_progress, filename="progress.png"),
            caption=(
                "📈 <b>Динамика твоего прогресса</b>\n\n"
                "Синяя линия — сон, желтая — качество."
            ),
            parse_mode="HTML",
        )
        os.remove(path_progress)

    await message.answer(
        "📌 Это твои графики за последние 30 дней. "
        "Чем больше дней — тем точнее анализ."
    )
    # --------------------------------------------------------
    # ГРАФИК 4: Смены (только если есть данные)
    # --------------------------------------------------------
    shift_chart = make_shift_chart(all_rows)  # <-- Передаем all_rows
    if shift_chart:
        await message.answer_photo(
            FSInputFile(shift_chart, filename="shift_sleep.png"),
            caption="🔄 <b>Сон по сменам</b>\n\nПоказывает, как ты спишь после разных типов смен.",
            parse_mode="HTML",
        )
        import os
        os.remove(shift_chart)