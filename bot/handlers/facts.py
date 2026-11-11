from aiogram import F, Router
from aiogram.types import Message

from bot.logic.sleep_facts import get_random_fact


router = Router()


@router.message(F.text == "💡 Факт про сон")
async def show_sleep_fact(message: Message):
    fact = get_random_fact()
    await message.answer(
        f"💡 Интересный факт про сон:\n\n{fact}"
    )