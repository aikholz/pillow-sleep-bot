from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.filters import CommandStart

from bot.keyboards.main import main_keyboard
from bot.states.registration import RegistrationStates
from bot.keyboards.registration import category_keyboard, schedule_keyboard
from bot.database.db import add_user, user_exists


router = Router()


@router.message(RegistrationStates.name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()

    if not name:
        await message.answer("Пожалуйста, напиши своё имя.")
        return

    await state.update_data(name=name)

    await message.answer(
        "Отлично! Теперь напиши свой возраст."
    )

    await state.set_state(RegistrationStates.age)


@router.message(RegistrationStates.age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer(
            "Возраст должен быть числом. Например: 20"
        )
        return

    age = int(message.text)

    if age < 10 or age > 100:
        await message.answer(
            "Пожалуйста, введи реальный возраст от 10 до 100 лет."
        )
        return

    await state.update_data(age=age)

    await message.answer(
        "Теперь выбери категорию, которая лучше всего "
        "описывает твой обычный график.",
        reply_markup=category_keyboard
    )

    await state.set_state(RegistrationStates.category)


@router.message(
    RegistrationStates.category,
    F.text.in_([
        "🧑‍💻 Офисный / умственный труд",
        "🌙 Сменный / ночной график",
        "🏃 Физический труд",
        "🎨 Свободный график / фриланс",
        "📚 Учебный график",
    ])
)
async def process_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text)

    await message.answer(
        "Теперь выбери свой обычный график:",
        reply_markup=schedule_keyboard
    )

    await state.set_state(RegistrationStates.schedule)


@router.message(RegistrationStates.category)
async def invalid_category(message: Message):
    await message.answer(
        "Пожалуйста, выбери одну из категорий кнопкой ниже.",
        reply_markup=category_keyboard
    )


@router.message(
    RegistrationStates.schedule,
    F.text.in_([
        "☀️ Дневной",
        "🌙 Ночной",
        "🔄 Сменный",
        "🕐 Свободный",
    ])
)
async def process_schedule(message: Message, state: FSMContext):
    await state.update_data(schedule=message.text)

    data = await state.get_data()

    # Защита от повторной регистрации
    if user_exists(message.from_user.id):
        await message.answer(
            "📌 Ты уже зарегистрирован(а) в «Подушке».\n\n"
            "Если хочешь изменить данные профиля — "
            "напиши /start, и я покажу главное меню.",
            reply_markup=main_keyboard
        )
        await state.clear()
        return

    add_user(
        telegram_id=message.from_user.id,
        name=data["name"],
        age=data["age"],
        category=data["category"],
        schedule=data["schedule"]
    )

    await message.answer(
        "Регистрация завершена! 😴\n\n"
        f"Имя: {data['name']}\n"
        f"Возраст: {data['age']}\n"
        f"Категория: {data['category']}\n"
        f"График: {data['schedule']}\n\n"
        "Теперь я могу начать отслеживать твой сон.",
        reply_markup=main_keyboard
    )

    await state.clear()


@router.message(RegistrationStates.schedule)
async def invalid_schedule(message: Message, state: FSMContext):
    await message.answer(
        "Пожалуйста, выбери график одной из кнопок.",
        reply_markup=schedule_keyboard
    )