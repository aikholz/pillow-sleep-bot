from datetime import date, timedelta
from aiogram import F, Router
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.database.db import (
    get_user,
    get_checkins_for_analysis,
    get_checkins_for_period,
)
from bot.logic.export import generate_csv, generate_pdf
import os

router = Router()


@router.message(F.text == "📤 Экспорт данных")
async def choose_format(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала пройди регистрацию через /start.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Скачать таблицу (CSV)", callback_data="export_csv")],
        [InlineKeyboardButton(text="📄 Скачать PDF-отчёт для врача", callback_data="export_pdf")]
    ])
    await message.answer("Выбери формат экспорта:", reply_markup=kb)


@router.callback_query(F.data == "export_csv")
async def export_csv_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    rows = get_checkins_for_analysis(telegram_id)

    if not rows:
        await callback.message.answer("Нет данных для экспорта.")
        await callback.answer()
        return

    await callback.message.answer("⏳ Формирую CSV-файл...")
    path = generate_csv(telegram_id) # Передаем ID, а не rows

    await callback.message.answer_document(
        FSInputFile(path, filename=f"sleep_data_{date.today().isoformat()}.csv"),
        caption="📊 Твои данные в формате CSV.\nМожно открыть в Excel или Google Таблицах."
    )
    os.remove(path)
    await callback.answer()


@router.callback_query(F.data == "export_pdf")
async def export_pdf_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    user = get_user(telegram_id)
    _, name, age, category, schedule = user

    rows = get_checkins_for_analysis(telegram_id)
    if not rows:
        await callback.message.answer("Нет данных для отчёта.")
        await callback.answer()
        return

    await callback.message.answer("⏳ Формирую PDF-отчёт...")
    period_start = date.today() - timedelta(days=30)
    period_rows = get_checkins_for_period(telegram_id, str(period_start), str(date.today()))

    user_info = {
        "name": name,
        "age": age,
        "category": category,
        "telegram_id": telegram_id,  # <-- ДОБАВЛЕНО
    }
    try:
        path = generate_pdf(rows, user_info, period_rows)
        await callback.message.answer_document(
            FSInputFile(path, filename=f"sleep_report_{date.today().isoformat()}.pdf"),
            caption="📄 Твой PDF-отчёт. Можно показать врачу или сохранить."
        )
        os.remove(path)
    except Exception as e:
        await callback.message.answer(f"Ошибка при создании PDF: {e}")

    await callback.answer()