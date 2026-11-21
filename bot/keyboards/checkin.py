from aiogram.types import (
    KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# ============================================================
# REPLY-КЛАВИАТУРЫ
# ============================================================

yes_no_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
    resize_keyboard=True,
)

time_suggestions_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="22:00"), KeyboardButton(text="22:30"), KeyboardButton(text="23:00")],
        [KeyboardButton(text="23:30"), KeyboardButton(text="00:00"), KeyboardButton(text="01:00")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

wake_time_suggestions_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="06:30"), KeyboardButton(text="07:00"), KeyboardButton(text="07:30")],
        [KeyboardButton(text="08:00"), KeyboardButton(text="08:30"), KeyboardButton(text="09:00")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


# ============================================================
# INLINE-КЛАВИАТУРЫ
# ============================================================

def _scale_inline(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="1 😫", callback_data=f"{prefix}_1"),
        InlineKeyboardButton(text="2 🙁", callback_data=f"{prefix}_2"),
        InlineKeyboardButton(text="3 😐", callback_data=f"{prefix}_3"),
        InlineKeyboardButton(text="4 🙂", callback_data=f"{prefix}_4"),
        InlineKeyboardButton(text="5 😄", callback_data=f"{prefix}_5"),
    ]])


def get_quality_inline() -> InlineKeyboardMarkup:
    """Оценка качества сна (1–5)."""
    return _scale_inline("ql")


def get_mood_inline() -> InlineKeyboardMarkup:
    """Оценка настроения (1–5)."""
    return _scale_inline("md")


def get_energy_inline() -> InlineKeyboardMarkup:
    """Оценка энергии (1–5)."""
    return _scale_inline("en")


def get_stress_inline() -> InlineKeyboardMarkup:
    """Оценка стресса (1–5)."""
    return _scale_inline("st")


def get_yes_no_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Да", callback_data="yes"),
        InlineKeyboardButton(text="Нет", callback_data="no"),
    ]])


def get_nap_duration_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="До 30 минут", callback_data="nap_30")],
        [InlineKeyboardButton(text="30–60 минут", callback_data="nap_60")],
        [InlineKeyboardButton(text="Больше часа", callback_data="nap_more")],
    ])


def get_caffeine_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Не пил(а)", callback_data="caf_0")],
        [InlineKeyboardButton(text="1 чашка", callback_data="caf_1")],
        [InlineKeyboardButton(text="2 чашки", callback_data="caf_2")],
        [InlineKeyboardButton(text="3 и более", callback_data="caf_3")],
    ])


def get_screen_time_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Не смотрел(а)", callback_data="scr_0")],
        [InlineKeyboardButton(text="До 30 минут", callback_data="scr_1")],
        [InlineKeyboardButton(text="30–60 минут", callback_data="scr_2")],
        [InlineKeyboardButton(text="Больше часа", callback_data="scr_3")],
    ])


def get_activity_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Не было", callback_data="act_0")],
        [InlineKeyboardButton(text="Лёгкая", callback_data="act_1")],
        [InlineKeyboardButton(text="Средняя", callback_data="act_2")],
        [InlineKeyboardButton(text="Высокая", callback_data="act_3")],
    ])


def get_shift_type_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Утро", callback_data="shift_Утро")],
        [InlineKeyboardButton(text="День", callback_data="shift_День")],
        [InlineKeyboardButton(text="Ночь", callback_data="shift_Ночь")],
        [InlineKeyboardButton(text="Выходной", callback_data="shift_Выходной")],
    ])


def get_night_shift_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Работал(а) ночью", callback_data="night_yes")],
        [InlineKeyboardButton(text="Не работал(а)", callback_data="night_no")],
    ])


def get_study_load_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Нет учебы", callback_data="study_0")],
        [InlineKeyboardButton(text="Средняя нагрузка", callback_data="study_1")],
        [InlineKeyboardButton(text="Сильная нагрузка", callback_data="study_2")],
    ])


def get_overwrite_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, перезаписать", callback_data="overwrite_yes")],
        [InlineKeyboardButton(text="❌ Нет, отмена", callback_data="overwrite_no")],
    ])