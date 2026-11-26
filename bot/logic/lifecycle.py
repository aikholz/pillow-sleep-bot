from datetime import date, timedelta

from bot.database.db import (
    get_first_checkin_date, get_checkins_for_analysis, get_user, get_user_status,
)
from bot.logic.sqi import compute_improvement
from bot.logic.sleep_model import build_sleep_profile


STABILIZE_DAYS = 14


def evaluate_progress(telegram_id):
    user = get_user(telegram_id)
    if not user:
        return "collecting"

    current_status = get_user_status(telegram_id)
    if current_status == "completed":
        return "completed"

    _, name, age, category, schedule = user
    rows = get_checkins_for_analysis(telegram_id)
    if len(rows) < 7:
        return "collecting"

    profile = build_sleep_profile(rows, age, schedule or "")
    target = profile.get("personal_target")
    imp = compute_improvement(rows, target)
    if not imp:
        return "baseline"

    habits_ok = imp.get("habits_pct", 0) >= 15
    if imp["delta_pct"] >= 10 or (habits_ok and imp["delta_pct"] >= 3):
        # Проверяем: не началась ли уже стабилизация
        # Ищем первый день, когда rolling SQI перевалил +10% к первому
        first_mean = imp["start_sqi"]
        threshold = first_mean * 1.10
        # Индекс дат: нужно понимать дату.
        first_date = get_first_checkin_date(telegram_id)
        if isinstance(first_date, str):
            from datetime import date as _d
            first_date = _d.fromisoformat(first_date)
        for idx, val in imp["rolling"]:
            if val >= threshold:
                # idx — позиция внутри rows (с фильтром по датам начала)
                stabilize_start = _date_for_index(telegram_id, idx)
                if not stabilize_start:
                    return "improving"
                days_since = (date.today() - stabilize_start).days
                if days_since >= STABILIZE_DAYS:
                    # Проверяем, что последние 3 дня держится
                    last3 = [s for _, s in imp["rolling"][-3:]]
                    if last3 and min(last3) >= threshold * 0.95:
                        return "completed"
                    return "stabilizing"
                return "stabilizing"
        return "improving"

    if imp["delta_pct"] <= -10:
        return "regression"

    return "baseline"

def _date_for_index(telegram_id, index_in_filtered_rows):
    """
    Возвращает дату по индексу строки в том же порядке, в котором их
    видит rolling_sqi (т.е. отфильтрованных по r[0] is not None,
    где r — из get_checkins_for_analysis, r[0] = sleep_duration).
    """
    from bot.database.db import get_checkins_with_dates
    rows = get_checkins_with_dates(telegram_id)

    # В get_checkins_with_dates:
    #   r[0] = checkin_date, r[1] = sleep_duration
    # Фильтруем по тому же признаку, что и rolling_sqi — по сну (r[1]).
    valid = [r for r in rows if r[1] is not None]

    if 0 <= index_in_filtered_rows < len(valid):
        d = valid[index_in_filtered_rows][0]
        return d if isinstance(d, date) else date.fromisoformat(str(d))
    return None


def stabilization_countdown(telegram_id):
    status = evaluate_progress(telegram_id)
    if status == "completed":
        return None  # <-- больше нечего отсчитывать
    if status != "stabilizing":
        return None
    _, name, age, category, schedule = user
    rows = get_checkins_for_analysis(telegram_id)
    profile = build_sleep_profile(rows, age, schedule or "")
    target = profile.get("personal_target")
    imp = compute_improvement(rows, target)
    if not imp:
        return None
    threshold = imp["start_sqi"] * 1.10
    for idx, val in imp["rolling"]:
        if val >= threshold:
            d = _date_for_index(telegram_id, idx)
            if d:
                passed = (date.today() - d).days
                left = max(0, STABILIZE_DAYS - passed)
                return left, STABILIZE_DAYS
    return None