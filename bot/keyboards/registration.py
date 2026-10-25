from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


category_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧑‍💻 Офисный / умственный труд")],
        [KeyboardButton(text="🌙 Сменный / ночной график")],
        [KeyboardButton(text="🏃 Физический труд")],
        [KeyboardButton(text="🎨 Свободный график / фриланс")],
        [KeyboardButton(text="📚 Учебный график")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)