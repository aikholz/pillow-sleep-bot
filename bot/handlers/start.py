from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states.registration import RegistrationStates
from bot.keyboards.main import main_keyboard
from bot.database.db import get_user


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)

    if user:
        _, name, age, category, schedule = user
        await state.clear()
        await message.answer(
            f"С возвращением, {name}! 😴\n\n"
            "Я «Подушка» и продолжаю отслеживать твой сон.\n\n"
            f"👤 {name}\n"
            f"🎂 Возраст: {age}\n"
            f"📌 Категория: {category}\n"
            f"🕐 График: {schedule}\n\n"
            "Выбери нужное действие:",
            reply_markup=main_keyboard
        )
        return

    await state.set_state(RegistrationStates.name)
    await message.answer(
        "Привет! Я «Подушка» 😴\n"
        "Я помогу тебе отслеживать сон и самочувствие.\n\n"
        "Давай сначала познакомимся!\n"
        "Как тебя зовут?"
    )


@router.message(Command("menu"))
async def show_menu(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return
    await message.answer("🏠 Главное меню\n\nВыбери нужное действие:", reply_markup=main_keyboard)