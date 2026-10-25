from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="😴 Отметить сон")],
        [
            KeyboardButton(text="📊 Моя статистика"),
            KeyboardButton(text="📈 Графики"),
        ],
        [
            KeyboardButton(text="📈 Первый отчёт"),
            KeyboardButton(text="🔎 Анализ"),
        ],
        [
            KeyboardButton(text="💡 Рекомендации"),
            KeyboardButton(text="📤 Экспорт данных"),
        ],
        [KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
)