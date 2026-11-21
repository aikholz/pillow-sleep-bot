from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="😴 Мой сон")],
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="📈 Мой прогресс"),
        ],
        [
            KeyboardButton(text="🔎 Анализ"),
            KeyboardButton(text="💡 Рекомендации"),
        ],
        [
            KeyboardButton(text="📤 Экспорт данных"),
            KeyboardButton(text="💡 Факт про сон"),
        ],
        [KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
)