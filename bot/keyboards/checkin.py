from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


quality_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="1"),
            KeyboardButton(text="2"),
            KeyboardButton(text="3"),
            KeyboardButton(text="4"),
            KeyboardButton(text="5"),
        ]
    ],
    resize_keyboard=True,
)


yes_no_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Да"),
            KeyboardButton(text="Нет"),
        ]
    ],
    resize_keyboard=True,
)


nap_duration_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="До 30 минут")],
        [KeyboardButton(text="30–60 минут")],
        [KeyboardButton(text="Больше часа")],
    ],
    resize_keyboard=True,
)


caffeine_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Не пил(а)")],
        [KeyboardButton(text="1 чашка")],
        [KeyboardButton(text="2 чашки")],
        [KeyboardButton(text="3 и более")],
    ],
    resize_keyboard=True,
)


screen_time_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Не смотрел(а)")],
        [KeyboardButton(text="До 30 минут")],
        [KeyboardButton(text="30–60 минут")],
        [KeyboardButton(text="Больше часа")],
    ],
    resize_keyboard=True,
)


activity_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Не было")],
        [KeyboardButton(text="Лёгкая")],
        [KeyboardButton(text="Средняя")],
        [KeyboardButton(text="Высокая")],
    ],
    resize_keyboard=True,
)