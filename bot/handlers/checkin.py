from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from bot.database.db import (
    add_checkin, has_checkin_for_date, get_user,
    get_checkins_for_analysis, is_course_completed, mark_course_completed,
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
from bot.logic.sqi import compute_improvement
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

# --- СМЕНА ---
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


# --- УЧЕБА ---
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


# --- КАЧЕСТВО СНА ---
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


# --- НАСТРОЕНИЕ ---
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


# --- ЭНЕРГИЯ ---
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


# --- ДНЕВНОЙ СОН ---
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


# --- КОФЕИН ---
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


# --- ЭКРАН ---
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


# --- АКТИВНОСТЬ ---
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


# --- СТРЕСС И СОХРАНЕНИЕ ---
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

    await callback.message.answer(
        "✅ Чек-ин полностью сохранён!\n\n"
        f"😴 Сон: {data['sleep_duration']:.1f} ч\n"
        f"⭐ Качество: {data['sleep_quality']}/5\n"
        f"🙂 Настроение: {data['mood']}/5\n"
        f"⚡ Энергия: {data['energy']}/5\n"
        f"😰 Стресс: {data['stress']}/5\n\n"
        "Спасибо! Данные будут использоваться для твоей статистики.",
        reply_markup=main_keyboard,
    )
    await state.clear()

    # ============ АНАЛИТИКА ПОСЛЕ СОХРАНЕНИЯ ============
    user = get_user(callback.from_user.id)
    if not user:
        return

    _, name, age, category, schedule = user
    rows = get_checkins_for_analysis(callback.from_user.id)
    profile = build_sleep_profile(rows, age, schedule or "")
    imp = compute_improvement(rows, profile.get("personal_target"))
    status = evaluate_progress(callback.from_user.id)

    extra_parts = []

    if imp and imp["delta_pct"] >= 10:
        extra_parts.append(
            f"📈 С начала отслеживания SQI сна вырос на {imp['delta_pct']:.0f}% "
            f"(привычки: +{imp['habits_pct']:.0f}%)."
        )
    elif imp and imp["delta_pct"] <= -10:
        extra_parts.append(
            f"📉 Твой SQI снизился на {abs(imp['delta_pct']):.0f}%. "
            "Это нормально — данные помогут скорректировать стратегию."
        )

    cd = stabilization_countdown(callback.from_user.id)
    if cd:
        left, total = cd
        if left > 0:
            extra_parts.append(
                f"🔒 Фаза стабилизации: осталось {left} из {total} дней. Продолжай держать привычки."
            )
        else:
            extra_parts.append("🎉 Стабилизация завершена — курс закрыт!")

    # 3 релевантные подсказки
    ctx = build_context(callback.from_user.id, rows)
    tips = select_tips(ctx, limit=3)
    if tips:
        tip_block = "💡 Что можно улучшить сегодня:\n" + "\n".join(
            f"{i}. {t}" for i, t in enumerate(tips, 1)
        )
        extra_parts.append(tip_block)

    if extra_parts:
        await callback.message.answer("\n\n".join(extra_parts))

    # Однократное поздравление по завершении
    if status == "completed" and not is_course_completed(callback.from_user.id):
        mark_course_completed(callback.from_user.id)
        await callback.message.answer(
            "🎉 Поздравляем — курс полностью завершён!\n"
            "Результат закреплён. Можешь продолжать вести дневник для поддержки."
        )


# ============================================================
# ТЕСТОВЫЕ ДАННЫЕ (без изменений)
# ============================================================

@router.message(F.text == "/test30")
async def create_educational_test_data(message: Message):
    from bot.database.db import SessionLocal, Checkin
    import random

    today = date.today()
    telegram_id = message.from_user.id

    with SessionLocal() as session:
        for i in range(30):
            checkin_date = today - timedelta(days=30 - i)

            if i % 3 == 0:
                study_load = 2
                sleep_duration = round(random.uniform(5.5, 6.5), 1)
                sleep_quality = random.randint(2, 3)
                mood = random.randint(2, 3)
                energy = random.randint(2, 3)
                stress = random.randint(4, 5)
                screen_time = "Больше часа"
                caffeine = "3 и более"
                caffeine_time = "19:00"
                physical_activity = "Не было"
                shift_type = "Учёба: Сильная"
                sleep_time = "02:00"
                wake_time = "08:00"
            elif i % 3 == 1:
                study_load = 1
                sleep_duration = round(random.uniform(6.5, 7.5), 1)
                sleep_quality = random.randint(3, 4)
                mood = random.randint(3, 4)
                energy = random.randint(3, 4)
                stress = random.randint(2, 3)
                screen_time = "30–60 минут"
                caffeine = "1 чашка"
                caffeine_time = "14:00"
                physical_activity = "Лёгкая"
                shift_type = "Учёба: Средняя"
                sleep_time = "00:00"
                wake_time = "07:30"
            else:
                study_load = 0
                sleep_duration = round(random.uniform(8.0, 9.0), 1)
                sleep_quality = random.randint(4, 5)
                mood = random.randint(4, 5)
                energy = random.randint(4, 5)
                stress = random.randint(1, 2)
                screen_time = "До 30 минут"
                caffeine = "Не пил(а)"
                caffeine_time = None
                physical_activity = "Высокая"
                shift_type = "Выходной"
                sleep_time = "23:00"
                wake_time = "08:30"

            checkin = session.query(Checkin).filter_by(
                telegram_id=telegram_id,
                checkin_date=checkin_date,
            ).first()

            values = {
                "sleep_time": sleep_time,
                "wake_time": wake_time,
                "sleep_duration": sleep_duration,
                "sleep_quality": sleep_quality,
                "mood": mood,
                "energy": energy,
                "nap_taken": 0,
                "nap_duration": None,
                "caffeine": caffeine,
                "caffeine_time": caffeine_time,
                "screen_time": screen_time,
                "physical_activity": physical_activity,
                "stress": stress,
                "shift_type": shift_type,
                "study_load": study_load,
            }

            if checkin:
                for key, value in values.items():
                    setattr(checkin, key, value)
            else:
                session.add(
                    Checkin(
                        telegram_id=telegram_id,
                        checkin_date=checkin_date,
                        **values,
                    )
                )

        session.commit()

    await message.answer(
        "🧪 Тестовые данные за 30 дней созданы!\n\n"
        "📚 График: Учебный\n"
        "📊 Включены дни с сильной, средней нагрузкой и выходные.\n\n"
        "Теперь нажми:\n"
        "📊 Статистика\n"
        "📈 Мой прогресс\n"
        "💡 Рекомендации"
    )