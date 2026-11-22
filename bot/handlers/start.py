from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states.registration import RegistrationStates
from bot.keyboards.main import main_keyboard
from bot.database.db import (
    get_user, get_checkins_for_analysis, is_course_completed, mark_course_completed,
)


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)

    if user:
        _, name, age, category, schedule = user
        await state.clear()

        # Проверка на завершённый курс и однократное поздравление
        if not is_course_completed(message.from_user.id):
            from bot.logic.lifecycle import evaluate_progress
            if evaluate_progress(message.from_user.id) == "completed":
                from bot.logic.sqi import daily_sqi
                from bot.logic.sleep_model import build_sleep_profile

                rows = get_checkins_for_analysis(message.from_user.id)
                profile = build_sleep_profile(rows, age, schedule or "")
                target = profile.get("personal_target")

                scored = [(daily_sqi(r, target), r) for r in rows if daily_sqi(r, target)]
                if scored:
                    scored.sort(key=lambda x: x[0])
                    worst, best = scored[0], scored[-1]

                    await message.answer(
                        "🎉 ПОЗДРАВЛЯЕМ! Твой курс завершён.\n\n"
                        f"🪫 Худший день в начале: {worst[0]:.0f} SQI\n"
                        f"   Сон {worst[1][0]:.1f} ч, качество {worst[1][1]}/5, "
                        f"стресс {worst[1][4]}/5\n\n"
                        f"⚡ Лучший день к финалу: {best[0]:.0f} SQI\n"
                        f"   Сон {best[1][0]:.1f} ч, качество {best[1][1]}/5, "
                        f"стресс {best[1][4]}/5\n\n"
                        "Можешь продолжить отслеживание или сделать паузу. "
                        "Напиши /start, чтобы вернуться."
                    )
                    mark_course_completed(message.from_user.id)

        await message.answer(
            f"С возвращением, {name}! 😴\n\n"
            "Я «Подушка» и продолжаю отслеживать твой сон.\n\n"
            f"👤 {name}\n"
            f"🎂 Возраст: {age}\n"
            f"📌 Категория: {category}\n"
            f"🕐 График: {schedule}\n\n"
            "Выбери нужное действие:",
            reply_markup=main_keyboard,
        )
        return

    await state.set_state(RegistrationStates.name)
    await message.answer(
        "Привет! Я «Подушка» 😴\n"
        "Я помогу тебе отслеживать сон и самочувствие.\n\n"
        "Давай сначала познакомимся!\n"
        "Как тебя зовут?"
    )