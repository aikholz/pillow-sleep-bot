from datetime import date, timedelta
from bot.database.db import (
    get_user, get_checkins_for_period, get_first_checkin_date, get_user_status
)


def evaluate_progress(telegram_id):
    """
    Проверяет, пора ли завершить курс.
    Возвращает статус: 'collecting', 'analyzing', 'stabilizing', 'completed'.
    """
    current_status = get_user_status(telegram_id)
    if current_status == "completed":
        return "completed"

    first_date_str = get_first_checkin_date(telegram_id)
    if not first_date_str:
        return "collecting"

    # get_first_checkin_date возвращает date (SQLAlchemy Date), не str
    if isinstance(first_date_str, str):
        first_date = date.fromisoformat(first_date_str)
    else:
        first_date = first_date_str

    days_passed = (date.today() - first_date).days

    rows = get_checkins_for_period(telegram_id, str(first_date), str(date.today()))

    if len(rows) < 5:
        return "collecting"

    if days_passed < 14:
        return "collecting" if len(rows) < 14 else "analyzing"

    if len(rows) >= 21:
        last_7_days = rows[-7:]
        good_days = sum(1 for r in last_7_days if r[2] >= 4 and r[1] >= 7)
        if good_days >= 5:
            return "completed"
        return "stabilizing"

    return "analyzing"