from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from bot.database.db import add_checkin, has_checkin_for_date, get_user
from bot.states.checkin import CheckinStates
from bot.keyboards.checkin import (
    quality_keyboard, yes_no_keyboard, nap_duration_keyboard,
    caffeine_keyboard, screen_time_keyboard, activity_keyboard,
    shift_type_shift_keyboard, shift_type_night_keyboard,
    shift_type_free_keyboard,
)
from bot.keyboards.main import main_keyboard

router = Router()

# Клавиатура для "Не спал"
no_sleep_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Не спал")]],
    resize_keyboard=True, one_time_keyboard=True
)

# Клавиатура для учебной нагрузки
study_load_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Нет учебы")],
        [KeyboardButton(text="Средняя нагрузка")],
        [KeyboardButton(text="Сильная нагрузка")],
    ],
    resize_keyboard=True, one_time_keyboard=True
)

# Клавиатура для подтверждения перезаписи
overwrite_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да, перезаписать"), KeyboardButton(text="Нет, отмена")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


@router.message(F.text == "😴 Отметить сон")
async def start_checkin(message: Message, state: FSMContext):
    yesterday = str(date.today() - timedelta(days=1))

    # Проверяем, есть ли уже чек-ин за вчера
    if has_checkin_for_date(message.from_user.id, yesterday):
        await message.answer(
            "📌 Ты уже заполнял(а) чек-ин за вчера.\n\n"
            "Хочешь перезаписать данные?",
            reply_markup=overwrite_keyboard
        )
        await state.set_state(CheckinStates.confirm_overwrite)
        return

    # Если нет — начинаем чек-ин
    await proceed_checkin(message, state)


@router.message(CheckinStates.confirm_overwrite, F.text == "Да, перезаписать")
async def confirm_overwrite_yes(message: Message, state: FSMContext):
    await proceed_checkin(message, state)


@router.message(CheckinStates.confirm_overwrite, F.text == "Нет, отмена")
async def confirm_overwrite_no(message: Message, state: FSMContext):
    await message.answer(
        "Хорошо, оставляем старые данные. Возвращаемся в меню.",
        reply_markup=main_keyboard
    )
    await state.clear()


@router.message(CheckinStates.confirm_overwrite)
async def invalid_overwrite(message: Message):
    await message.answer(
        "Пожалуйста, выбери «Да, перезаписать» или «Нет, отмена».",
        reply_markup=overwrite_keyboard
    )


async def proceed_checkin(message: Message, state: FSMContext):
    """Основная логика чек-ина (без проверки на дубликат)."""
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    _, name, age, category, schedule = user
    schedule = schedule or ""
    category = category or ""

    await state.update_data(user_schedule=schedule, user_category=category)

    # Учебный график
    if "Учебный" in category or "Учебный" in schedule:
        await message.answer(
            "Начинаем чек-ин за вчера 😴\n\n"
            "Какая вчера была учебная нагрузка?",
            reply_markup=study_load_keyboard,
        )
        await state.set_state(CheckinStates.study_load)
        return

    if "Сменный" in schedule or "Сменный" in category:
        await message.answer(
            "Начинаем чек-ин за вчера 😴\n\n"
            "Какая вчера была смена?",
            reply_markup=shift_type_shift_keyboard,
        )
        await state.set_state(CheckinStates.shift_type)
        return

    if "Ночной" in schedule or "ночной" in category.lower():
        await message.answer(
            "Начинаем чек-ин за вчера 😴\n\n"
            "Ты работал(а) вчера ночью?",
            reply_markup=shift_type_night_keyboard,
        )
        await state.set_state(CheckinStates.shift_type)
        return

    if "Свободный" in schedule or "фриланс" in category.lower():
        await message.answer(
            "Начинаем чек-ин за вчера 😴\n\n"
            "Вчера был рабочий день?",
            reply_markup=shift_type_free_keyboard,
        )
        await state.set_state(CheckinStates.shift_type)
        return

    await state.update_data(shift_type=None, study_load=0)
    await ask_sleep_time(message, state)


@router.message(CheckinStates.study_load)
async def process_study_load(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "Нет учебы":
        load = 0
        shift_type = "Выходной"
    elif text == "Средняя нагрузка":
        load = 1
        shift_type = "Учёба: Средняя"
    elif text == "Сильная нагрузка":
        load = 2
        shift_type = "Учёба: Сильная"
    else:
        await message.answer("Пожалуйста, выбери вариант кнопкой ниже 👇", reply_markup=study_load_keyboard)
        return

    await state.update_data(study_load=load, shift_type=shift_type)
    await ask_sleep_time(message, state)


@router.message(CheckinStates.shift_type)
async def process_shift_type(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "Работал(а) ночью":
        shift_type = "Ночь"
    elif text == "Не работал(а)":
        shift_type = "Выходной"
    elif text == "Рабочий день":
        shift_type = "Рабочий"
    elif text == "Свободный день":
        shift_type = "Свободный"
    elif text in ["Утро", "День", "Ночь", "Выходной"]:
        shift_type = text
    else:
        await message.answer("Пожалуйста, выбери вариант кнопкой ниже.")
        return

    await state.update_data(shift_type=shift_type, study_load=0)
    await ask_sleep_time(message, state)


async def ask_sleep_time(message: Message, state: FSMContext):
    await message.answer(
        "Во сколько ты вчера лёг(ла) спать?\n"
        "Напиши время в формате ЧЧ:ММ (например, 23:30).\n\n"
        "Если не спал(а) вообще — нажми кнопку ниже.",
        reply_markup=no_sleep_keyboard
    )
    await state.set_state(CheckinStates.sleep_time)


@router.message(CheckinStates.sleep_time)
async def process_sleep_time(message: Message, state: FSMContext):
    if message.text.strip().lower() == "не спал":
        await state.update_data(sleep_time="00:00", wake_time="00:00", sleep_duration=0)
        await message.answer(
            "Понял, вчера без сна. Как оценишь качество?",
            reply_markup=quality_keyboard
        )
        await state.set_state(CheckinStates.sleep_quality)
        return

    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Введи время в формате ЧЧ:ММ.\nНапример: 23:30")
        return

    await state.update_data(sleep_time=message.text.strip())
    await message.answer(
        "Во сколько ты вчера проснулся(лась)?\nНапример: 07:30",
        reply_markup=ReplyKeyboardRemove()
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
        "Как ты оцениваешь качество сна?\n\n1 — очень плохое\n5 — отличное",
        reply_markup=quality_keyboard
    )
    await state.set_state(CheckinStates.sleep_quality)


@router.message(CheckinStates.sleep_quality, F.text.in_(["1", "2", "3", "4", "5"]))
async def process_sleep_quality(message: Message, state: FSMContext):
    await state.update_data(sleep_quality=int(message.text))
    await message.answer(
        "Какое у тебя настроение после сна?\nОцени от 1 до 5.",
        reply_markup=quality_keyboard
    )
    await state.set_state(CheckinStates.mood)


@router.message(CheckinStates.mood, F.text.in_(["1", "2", "3", "4", "5"]))
async def process_mood(message: Message, state: FSMContext):
    await state.update_data(mood=int(message.text))
    await message.answer(
        "Какой у тебя уровень энергии после сна?\nОцени от 1 до 5.",
        reply_markup=quality_keyboard
    )
    await state.set_state(CheckinStates.energy)


@router.message(CheckinStates.energy, F.text.in_(["1", "2", "3", "4", "5"]))
async def process_energy(message: Message, state: FSMContext):
    await state.update_data(energy=int(message.text))
    await message.answer("Ты вчера спал(а) днём?", reply_markup=yes_no_keyboard)
    await state.set_state(CheckinStates.nap)


@router.message(CheckinStates.nap, F.text == "Да")
async def process_yes_nap(message: Message, state: FSMContext):
    await state.update_data(nap_taken=1)
    await message.answer("Сколько примерно длился дневной сон?", reply_markup=nap_duration_keyboard)
    await state.set_state(CheckinStates.nap_duration)


@router.message(CheckinStates.nap, F.text == "Нет")
async def process_no_nap(message: Message, state: FSMContext):
    await state.update_data(nap_taken=0, nap_duration=None)
    await ask_caffeine(message, state)


@router.message(CheckinStates.nap_duration, F.text.in_(["До 30 минут", "30–60 минут", "Больше часа"]))
async def process_nap_duration(message: Message, state: FSMContext):
    await state.update_data(nap_duration=message.text)
    await ask_caffeine(message, state)


async def ask_caffeine(message: Message, state: FSMContext):
    await message.answer(
        "☕ Сколько порций кофеина (кофе, чай, энергетик) ты выпил(а) вчера?\n\nВыбери вариант кнопкой ниже:",
        reply_markup=caffeine_keyboard
    )
    await state.set_state(CheckinStates.caffeine)


@router.message(CheckinStates.caffeine, F.text.in_(["Не пил(а)", "1 чашка", "2 чашки", "3 и более"]))
async def process_caffeine(message: Message, state: FSMContext):
    await state.update_data(caffeine=message.text)
    if message.text == "Не пил(а)":
        await state.update_data(caffeine_time=None)
        await ask_screen_time(message, state)
        return

    await message.answer(
        "Во сколько была последняя чашка кофеина вчера?\n\nНапиши время в формате ЧЧ:ММ (например, 16:30).",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(CheckinStates.caffeine_time)


@router.message(CheckinStates.caffeine_time)
async def process_caffeine_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Введи время в формате ЧЧ:ММ.\nНапример: 16:30")
        return
    await state.update_data(caffeine_time=message.text.strip())
    await ask_screen_time(message, state)


async def ask_screen_time(message: Message, state: FSMContext):
    await message.answer(
        "Сколько времени ты провёл(а) за экраном в последние 2 часа перед сном?",
        reply_markup=screen_time_keyboard
    )
    await state.set_state(CheckinStates.screen_time)


@router.message(CheckinStates.screen_time, F.text.in_(["Не смотрел(а)", "До 30 минут", "30–60 минут", "Больше часа"]))
async def process_screen_time(message: Message, state: FSMContext):
    await state.update_data(screen_time=message.text)
    await message.answer("Какая физическая активность была вчера?", reply_markup=activity_keyboard)
    await state.set_state(CheckinStates.physical_activity)


@router.message(CheckinStates.physical_activity, F.text.in_(["Не было", "Лёгкая", "Средняя", "Высокая"]))
async def process_physical_activity(message: Message, state: FSMContext):
    await state.update_data(physical_activity=message.text)
    await message.answer(
        "Какой у тебя был уровень стресса вчера?\nОцени от 1 до 5.",
        reply_markup=quality_keyboard
    )
    await state.set_state(CheckinStates.stress)


@router.message(CheckinStates.stress, F.text.in_(["1", "2", "3", "4", "5"]))
async def process_stress(message: Message, state: FSMContext):
    await state.update_data(stress=int(message.text))
    data = await state.get_data()

    # Сохраняем за ВЧЕРА
    yesterday = str(date.today() - timedelta(days=1))

    add_checkin(
        telegram_id=message.from_user.id,
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
        study_load=data.get("study_load", 0)
    )

    await message.answer(
        "✅ Чек-ин полностью сохранён!\n\n"
        f"😴 Сон: {data['sleep_duration']:.1f} ч\n"
        f"⭐ Качество: {data['sleep_quality']}/5\n"
        f"🙂 Настроение: {data['mood']}/5\n"
        f"⚡ Энергия: {data['energy']}/5\n"
        f"😰 Стресс: {data['stress']}/5\n\n"
        "Спасибо! Данные будут использоваться для твоей статистики и рекомендаций.",
        reply_markup=main_keyboard
    )
    await state.clear()


# --- ОБРАБОТЧИКИ ОШИБОК ---
@router.message(CheckinStates.caffeine)
async def invalid_caffeine(message: Message):
    await message.answer("Пожалуйста, выбери вариант кнопкой ниже 👇", reply_markup=caffeine_keyboard)

@router.message(CheckinStates.sleep_quality)
async def invalid_quality(message: Message):
    await message.answer("Пожалуйста, выбери оценку от 1 до 5 кнопкой ниже 👇", reply_markup=quality_keyboard)

@router.message(CheckinStates.mood)
async def invalid_mood(message: Message):
    await message.answer("Пожалуйста, выбери оценку от 1 до 5 кнопкой ниже 👇", reply_markup=quality_keyboard)

@router.message(CheckinStates.energy)
async def invalid_energy(message: Message):
    await message.answer("Пожалуйста, выбери оценку от 1 до 5 кнопкой ниже 👇", reply_markup=quality_keyboard)

@router.message(CheckinStates.stress)
async def invalid_stress(message: Message):
    await message.answer("Пожалуйста, выбери оценку от 1 до 5 кнопкой ниже 👇", reply_markup=quality_keyboard)

@router.message(CheckinStates.nap)
async def invalid_nap(message: Message):
    await message.answer("Пожалуйста, выбери «Да» или «Нет» кнопкой ниже 👇", reply_markup=yes_no_keyboard)

@router.message(CheckinStates.screen_time)
async def invalid_screen(message: Message):
    await message.answer("Пожалуйста, выбери вариант кнопкой ниже 👇", reply_markup=screen_time_keyboard)

@router.message(CheckinStates.physical_activity)
async def invalid_activity(message: Message):
    await message.answer("Пожалуйста, выбери вариант кнопкой ниже 👇", reply_markup=activity_keyboard)


# --- ТЕСТОВЫЕ ДАННЫЕ ---
@router.message(F.text == "/test5")
async def create_test_checkins(message: Message):
    from bot.database.db import create_test_data
    create_test_data(message.from_user.id)
    await message.answer("🧪 Тестовые данные созданы!\n\nСоздано 7 дней чек-инов.")

@router.message(F.text == "/test28")
async def create_personal_test_checkins(message: Message):
    from bot.database.db import create_personal_test_data
    create_personal_test_data(message.from_user.id)
    await message.answer("🧪 Персональный тестовый набор создан!\n\nСоздано 28 дней данных.")