# bot/handlers/checkin.py
from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from bot.database.db import (
    add_checkin, has_checkin_for_date, get_user,
    get_checkins_for_analysis, is_course_completed, mark_course_completed,
    get_first_checkin_date,
)
from bot.states.checkin import CheckinStates
from bot.keyboards.checkin import (
    get_quality_inline, get_mood_inline, get_energy_inline, get_stress_inline,
    get_yes_no_inline, get_nap_duration_inline,
    get_caffeine_inline, get_screen_time_inline, get_activity_inline,
    get_shift_type_inline, get_night_shift_inline, get_study_load_inline,
    get_overwrite_inline, time_suggestions_keyboard, wake_time_suggestions_keyboard,
)
from bot.keyboards.main import main_keyboard
from bot.logic.reminders import build_context, select_tips
from bot.logic.lifecycle import stabilization_countdown, evaluate_progress
from bot.logic.sqi import compute_improvement, daily_sqi
from bot.logic.sleep_model import build_sleep_profile

router = Router()

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ
# ============================================================

def get_progress_bar(step: int, total: int = 12) -> str:
    filled = "■" * step
    empty = "□" * (total - step)
    return f"[{filled}{empty}] {step}/{total}\n\n"


async def delete_previous_msg(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass


# ============================================================
# СТАРТ ЧЕК-ИНА
# ============================================================

@router.message(F.text == "😴 Мой сон")
async def start_checkin(message: Message, state: FSMContext):
    yesterday = str(date.today() - timedelta(days=1))

    if has_checkin_for_date(message.from_user.id, yesterday):
        await message.answer(
            "📌 Ты уже заполнял(а) чек-ин за вчера.\n\nХочешь перезаписать данные?",
            reply_markup=get_overwrite_inline(),
        )
        await state.set_state(CheckinStates.confirm_overwrite)
        return

    await proceed_checkin(message, state)


@router.callback_query(F.data == "overwrite_yes", CheckinStates.confirm_overwrite)
async def confirm_overwrite_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await delete_previous_msg(callback)
    await proceed_checkin(callback.message, state)


@router.callback_query(F.data == "overwrite_no", CheckinStates.confirm_overwrite)
async def confirm_overwrite_no(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await delete_previous_msg(callback)
    await callback.message.answer("Хорошо, оставляем старые данные.", reply_markup=main_keyboard)
    await state.clear()


async def proceed_checkin(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    _, name, age, category, schedule = user
    schedule = schedule or ""
    category = category or ""

    await state.update_data(user_schedule=schedule, user_category=category)

    if "Учебный" in category or "Учебный" in schedule:
        await message.answer(
            get_progress_bar(1) + "Какая вчера была учебная нагрузка?",
            reply_markup=get_study_load_inline(),
        )
        await state.set_state(CheckinStates.study_load)
        return

    if "Сменный" in schedule or "Сменный" in category:
        await message.answer(
            get_progress_bar(1) + "Какая вчера была смена?",
            reply_markup=get_shift_type_inline(),
        )
        await state.set_state(CheckinStates.shift_type)
        return

    if "Ночной" in schedule or "ночной" in category.lower():
        await message.answer(
            get_progress_bar(1) + "Ты работал(а) вчера ночью?",
            reply_markup=get_night_shift_inline(),
        )
        await state.set_state(CheckinStates.shift_type)
        return

    await state.update_data(shift_type=None, study_load=0)
    await ask_sleep_time(message, state)


# ============================================================
# ШАГИ ЧЕК-ИНА
# ============================================================

async def ask_sleep_time(message: Message, state: FSMContext):
    await message.answer(
        get_progress_bar(1) +
        "Во сколько ты вчера лёг(ла) спать?\n"
        "Напиши время в формате ЧЧ:ММ или выбери кнопку ниже.\n\n"
        "Если не спал(а) — напиши «Не спал».",
        reply_markup=time_suggestions_keyboard,
    )
    await state.set_state(CheckinStates.sleep_time)


@router.message(CheckinStates.sleep_time)
async def process_sleep_time(message: Message, state: FSMContext):
    if message.text.strip().lower() == "не спал":
        await state.update_data(
            sleep_time="00:00", wake_time="00:00",
            sleep_duration=0, sleep_quality=0,
        )
        await message.answer(
            get_progress_bar(3) + "Понял, вчера без сна.\n\nКакое у тебя настроение после сна?",
            reply_markup=get_mood_inline(),
        )
        await state.set_state(CheckinStates.mood)
        return

    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Введи время в формате ЧЧ:ММ (например, 23:30).")
        return

    await state.update_data(sleep_time=message.text.strip())
    await message.answer(
        get_progress_bar(2) +
        "Во сколько ты вчера проснулся(лась)?\n"
        "Выбери кнопку или напиши время (например, 07:30).",
        reply_markup=wake_time_suggestions_keyboard,
    )
    await state.set_state(CheckinStates.wake_time)


@router.message(CheckinStates.wake_time)
async def process_wake_time(message: Message, state: FSMContext):
    try:
        wake_time = datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Введи время в формате ЧЧ:ММ.\nНапример: 07:30")
        return

    data = await state.get_data()
    sleep_time = datetime.strptime(data["sleep_time"], "%H:%M")

    if wake_time <= sleep_time:
        wake_time += timedelta(days=1)

    sleep_duration = (wake_time - sleep_time).total_seconds() / 3600
    if sleep_duration <= 0 or sleep_duration > 24:
        await message.answer("Не удалось определить продолжительность сна. Проверь время.")
        return

    await state.update_data(wake_time=message.text.strip(), sleep_duration=sleep_duration)

    await message.answer(
        get_progress_bar(3) + "Как ты оцениваешь качество сна?",
        reply_markup=get_quality_inline(),
    )
    await state.set_state(CheckinStates.sleep_quality)


# ============================================================
# INLINE-ОБРАБОТЧИКИ
# ============================================================

@router.callback_query(F.data.startswith("shift_"), CheckinStates.shift_type)
async def process_shift_inline(callback: CallbackQuery, state: FSMContext):
    shift_type = callback.data.replace("shift_", "")
    await state.update_data(shift_type=shift_type, study_load=0)
    await callback.answer()
    await delete_previous_msg(callback)
    await ask_sleep_time(callback.message, state)


@router.callback_query(F.data.startswith("night_"), CheckinStates.shift_type)
async def process_night_inline(callback: CallbackQuery, state: FSMContext):
    shift_type = "Ночь" if callback.data == "night_yes" else "Выходной"
    await state.update_data(shift_type=shift_type, study_load=0)
    await callback.answer()
    await delete_previous_msg(callback)
    await ask_sleep_time(callback.message, state)


@router.callback_query(F.data.startswith("study_"), CheckinStates.study_load)
async def process_study_inline(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[1])
    if val == 0:
        shift_type = "Выходной"
    elif val == 1:
        shift_type = "Учёба: Средняя"
    else:
        shift_type = "Учёба: Сильная"

    await state.update_data(study_load=val, shift_type=shift_type)
    await callback.answer()
    await delete_previous_msg(callback)
    await ask_sleep_time(callback.message, state)


@router.callback_query(F.data.startswith("ql_"), CheckinStates.sleep_quality)
async def process_quality_inline(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[1])
    await state.update_data(sleep_quality=val)
    await callback.answer()
    await delete_previous_msg(callback)
    await callback.message.answer(
        get_progress_bar(4) + "Какое у тебя настроение после сна?",
        reply_markup=get_mood_inline(),
    )
    await state.set_state(CheckinStates.mood)


@router.callback_query(F.data.startswith("md_"), CheckinStates.mood)
async def process_mood_inline(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[1])
    await state.update_data(mood=val)
    await callback.answer()
    await delete_previous_msg(callback)
    await callback.message.answer(
        get_progress_bar(5) + "Какой у тебя уровень энергии после сна?",
        reply_markup=get_energy_inline(),
    )
    await state.set_state(CheckinStates.energy)


@router.callback_query(F.data.startswith("en_"), CheckinStates.energy)
async def process_energy_inline(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[1])
    await state.update_data(energy=val)
    await callback.answer()
    await delete_previous_msg(callback)
    await callback.message.answer(
        get_progress_bar(6) + "Ты вчера спал(а) днём?",
        reply_markup=get_yes_no_inline(),
    )
    await state.set_state(CheckinStates.nap)


@router.callback_query(F.data == "yes", CheckinStates.nap)
async def process_nap_yes(callback: CallbackQuery, state: FSMContext):
    await state.update_data(nap_taken=1)
    await callback.answer()
    await delete_previous_msg(callback)
    await callback.message.answer(
        get_progress_bar(7) + "Сколько примерно длился дневной сон?",
        reply_markup=get_nap_duration_inline(),
    )
    await state.set_state(CheckinStates.nap_duration)


@router.callback_query(F.data == "no", CheckinStates.nap)
async def process_nap_no(callback: CallbackQuery, state: FSMContext):
    await state.update_data(nap_taken=0, nap_duration=None)
    await callback.answer()
    await delete_previous_msg(callback)
    await callback.message.answer(
        get_progress_bar(8) + "☕ Сколько порций кофеина ты выпил(а) вчера?",
        reply_markup=get_caffeine_inline(),
    )
    await state.set_state(CheckinStates.caffeine)


@router.callback_query(F.data.startswith("nap_"), CheckinStates.nap_duration)
async def process_nap_duration_inline(callback: CallbackQuery, state: FSMContext):
    mapping = {"nap_30": "До 30 минут", "nap_60": "30–60 минут", "nap_more": "Больше часа"}
    await state.update_data(nap_duration=mapping[callback.data])
    await callback.answer()
    await delete_previous_msg(callback)
    await callback.message.answer(
        get_progress_bar(8) + "☕ Сколько порций кофеина ты выпил(а) вчера?",
        reply_markup=get_caffeine_inline(),
    )
    await state.set_state(CheckinStates.caffeine)


@router.callback_query(F.data.startswith("caf_"), CheckinStates.caffeine)
async def process_caffeine_inline(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[1])
    mapping = {0: "Не пил(а)", 1: "1 чашка", 2: "2 чашки", 3: "3 и более"}
    await state.update_data(caffeine=mapping[val])
    await callback.answer()
    await delete_previous_msg(callback)

    if val == 0:
        await state.update_data(caffeine_time=None)
        await callback.message.answer(
            get_progress_bar(10) + "Сколько времени ты провёл(а) за экраном перед сном?",
            reply_markup=get_screen_time_inline(),
        )
        await state.set_state(CheckinStates.screen_time)
        return

    await callback.message.answer(
        get_progress_bar(9) + "Во сколько была последняя чашка кофеина? (ЧЧ:ММ)",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(CheckinStates.caffeine_time)


@router.message(CheckinStates.caffeine_time)
async def process_caffeine_time_text(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Введи время в формате ЧЧ:ММ.\nНапример: 16:30")
        return
    await state.update_data(caffeine_time=message.text.strip())
    await message.answer(
        get_progress_bar(10) + "Сколько времени ты провёл(а) за экраном перед сном?",
        reply_markup=get_screen_time_inline(),
    )
    await state.set_state(CheckinStates.screen_time)


@router.callback_query(F.data.startswith("scr_"), CheckinStates.screen_time)
async def process_screen_inline(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[1])
    mapping = {0: "Не смотрел(а)", 1: "До 30 минут", 2: "30–60 минут", 3: "Больше часа"}
    await state.update_data(screen_time=mapping[val])
    await callback.answer()
    await delete_previous_msg(callback)
    await callback.message.answer(
        get_progress_bar(11) + "Какая физическая активность была вчера?",
        reply_markup=get_activity_inline(),
    )
    await state.set_state(CheckinStates.physical_activity)


@router.callback_query(F.data.startswith("act_"), CheckinStates.physical_activity)
async def process_activity_inline(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[1])
    mapping = {0: "Не было", 1: "Лёгкая", 2: "Средняя", 3: "Высокая"}
    await state.update_data(physical_activity=mapping[val])
    await callback.answer()
    await delete_previous_msg(callback)
    await callback.message.answer(
        get_progress_bar(12) + "Какой у тебя был уровень стресса вчера?",
        reply_markup=get_stress_inline(),
    )
    await state.set_state(CheckinStates.stress)


# ============================================================
# СТРЕСС + СОХРАНЕНИЕ + АНАЛИТИКА
# ============================================================

@router.callback_query(F.data.startswith("st_"), CheckinStates.stress)
async def process_stress_inline(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[1])
    await state.update_data(stress=val)
    await callback.answer()
    await delete_previous_msg(callback)

    data = await state.get_data()
    yesterday = str(date.today() - timedelta(days=1))

    add_checkin(
        telegram_id=callback.from_user.id,
        checkin_date=yesterday,
        sleep_time=data["sleep_time"],
        wake_time=data["wake_time"],
        sleep_duration=data["sleep_duration"],
        sleep_quality=data["sleep_quality"],
        mood=data["mood"],
        energy=data["energy"],
        nap_taken=data["nap_taken"],
        nap_duration=data.get("nap_duration"),
        caffeine=data["caffeine"],
        caffeine_time=data.get("caffeine_time"),
        screen_time=data["screen_time"],
        physical_activity=data["physical_activity"],
        stress=data["stress"],
        shift_type=data.get("shift_type"),
        study_load=data.get("study_load", 0),
    )

    # Базовое подтверждение
    await callback.message.answer(
        "✅ Чек-ин полностью сохранён!\n\n"
        f"😴 Сон: {data['sleep_duration']:.1f} ч\n"
        f"⭐ Качество: {data['sleep_quality']}/5\n"
        f"🙂 Настроение: {data['mood']}/5\n"
        f"⚡ Энергия: {data['energy']}/5\n"
        f"😰 Стресс: {data['stress']}/5",
        reply_markup=main_keyboard,
    )
    await state.clear()

    # ============ АНАЛИТИКА ПОСЛЕ СОХРАНЕНИЯ ============
    await send_post_checkin_insights(callback.message, callback.from_user.id)


# ============================================================
# ПОСТ-АНАЛИТИКА
# ============================================================

async def send_post_checkin_insights(message: Message, telegram_id: int):
    user = get_user(telegram_id)
    if not user:
        return

    _, name, age, category, schedule = user
    schedule = schedule or ""
    category = category or ""

    rows = get_checkins_for_analysis(telegram_id)
    profile = build_sleep_profile(rows, age, schedule)
    target = profile.get("personal_target")
    imp = compute_improvement(rows, target)
    status = evaluate_progress(telegram_id)
    cd = stabilization_countdown(telegram_id)

    extra_parts: list[str] = []

    # --- 1. Прогресс SQI (только когда данных достаточно) ---
    if imp and imp["days"] >= 7:
        delta = imp["delta_pct"]
        hab = imp["habits_pct"]
        arrow = "📈" if delta > 0 else ("📉" if delta < 0 else "➖")

        if delta >= 3 or hab >= 5:
            if hab >= 5 and delta < 3:
                extra_parts.append(
                    f"👟 Привычки улучшились на {hab:+.0f}% — это уже влияет на качество. "
                    "SQI подтянется вслед за ними."
                )
            else:
                extra_parts.append(
                    f"{arrow} С начала отслеживания качество сна изменилось на {delta:+.0f}%."
                )
                if hab >= 5:
                    extra_parts.append(f"👟 Привычки улучшились на {hab:+.0f}%.")
        elif delta <= -10:
            extra_parts.append(
                f"📉 SQI снизился на {abs(delta):.0f}%. Это нормально — "
                "данные помогают скорректировать стратегию."
            )

    # --- 2. Фаза стабилизации / завершение ---
    if cd:
        left, total = cd
        if left > 0:
            extra_parts.append(
                f"🔒 Фаза стабилизации: осталось {left} из {total} дней. "
                "Продолжай держать привычки — организм закрепляет результат."
            )
        else:
            extra_parts.append("🎉 Стабилизация завершена — курс закрыт!")

    # --- 3. Сравнение худшего/лучшего дня при завершении ---
    if status == "completed" and not is_course_completed(telegram_id):
        compare_text = _build_completion_compare(rows, target)
        if compare_text:
            extra_parts.append(compare_text)
        mark_course_completed(telegram_id)

    # --- 4. Рекомендации по контексту (с учётом графика) ---
    ctx = build_context(telegram_id, rows)
    ctx = _enrich_context_by_schedule(ctx, category, schedule, profile)
    tips = select_tips(ctx, limit=3)

    if tips:
        # Нумерованный, аккуратный вывод
        numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(tips, 1))
        extra_parts.append("💡 Что можно улучшить сегодня:\n" + numbered)

    if extra_parts:
        await message.answer("\n\n".join(extra_parts))


# ============================================================
# СРАВНЕНИЕ ХУДШЕГО И ЛУЧШЕГО ДНЯ
# ============================================================

def _build_completion_compare(rows, target):
    scored = []
    for r in rows:
        sqi = daily_sqi(r, target)
        if sqi is not None:
            scored.append((sqi, r))

    if len(scored) < 7:
        return None

    scored.sort(key=lambda x: x[0])
    worst, best = scored[0], scored[-1]

    def fmt(day):
        sqi, r = day
        sleep = r[0] if r[0] is not None else 0
        qual = r[1] if r[1] is not None else 0
        stress = r[4] if r[4] is not None else 0
        return (
            f"SQI {sqi:.0f}\n"
            f"   😴 {sleep:.1f} ч, ⭐ {qual}/5, 😰 стресс {stress}/5"
        )

    return (
        "🏁 СРАВНЕНИЕ ДО / ПОСЛЕ\n\n"
        f"🪫 Худший день:\n{fmt(worst)}\n\n"
        f"⚡ Лучший день:\n{fmt(best)}\n\n"
        "📌 Можешь продолжать вести дневник — данные помогут удерживать результат."
    )


# ============================================================
# ДОП. КОНТЕКСТ ПО ГРАФИКУ
# ============================================================

def _enrich_context_by_schedule(ctx: dict, category: str, schedule: str, profile: dict) -> dict:
    """
    Добавляет в контекст флаги для советов, специфичных для графика.
    Используется в select_tips (см. ниже).
    """
    ctx = dict(ctx)  # не мутируем исходный

    total_sleep_mode = profile.get("total_sleep_mode", False)
    ctx["total_sleep_mode"] = total_sleep_mode

    # Для сменных/ночных — приоритет советов про свет и восстановление
    ctx["is_shift"] = ("Сменный" in category) or ("Сменный" in schedule)
    ctx["is_night"] = ("Ночной" in category) or ("Ночной" in schedule) or ("ночной" in category.lower())
    ctx["is_student"] = "Учебный" in category or "Учебный" in schedule
    ctx["is_office"] = "Офисный" in category
    ctx["is_physical"] = "Физический" in category
    ctx["is_freelance"] = "Свободный" in category or "Свободный" in schedule

    return ctx