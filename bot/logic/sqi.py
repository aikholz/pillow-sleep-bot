from datetime import date, datetime, timedelta
from statistics import mean

from bot.logic.sleep_model import (
    caffeine_to_number, screen_to_number, activity_to_number,
    build_sleep_profile, caffeine_hours_before_sleep,
)


def _time_score(sleep_time_str):
    """1.0 — до 23:00, линейно до 0.4 к 02:00, 0.3 — позже."""
    if not sleep_time_str:
        return 0.5
    try:
        h, m = map(int, sleep_time_str.split(":"))
    except ValueError:
        return 0.5
    if h < 12:
        h += 24
    minutes = h * 60 + m
    if minutes <= 23 * 60:
        return 1.0
    if minutes <= 24 * 60:
        return 1.0 - 0.1 * (minutes - 23 * 60) / 60
    if minutes <= 26 * 60:
        return 0.9 - 0.5 * (minutes - 24 * 60) / 120
    return 0.3


def _sleep_target_score(sleep, target):
    """1.0 — в диапазоне target±0.5; штраф за недосып/пересып."""
    if sleep is None or target is None:
        return 0.5
    diff = abs(sleep - target)
    if diff <= 0.5:
        return 1.0
    if diff <= 1.0:
        return 0.85
    if diff <= 1.5:
        return 0.65
    if diff <= 2.0:
        return 0.45
    if sleep < 5:
        return 0.2
    if sleep > 9.5:
        return 0.25
    return 0.3


def _habits_score(row):
    """0..1 по привычкам + бонусы."""
    caf = caffeine_to_number(row[5]) if len(row) > 5 else 0
    scr = screen_to_number(row[7]) if len(row) > 7 else 0
    act = activity_to_number(row[8]) if len(row) > 8 else 0
    sleep_time = row[11] if len(row) > 11 else None
    caf_time = row[6] if len(row) > 6 else None

    caf_score = 1 - caf / 3
    scr_score = 1 - scr / 3
    act_score = act / 3
    time_score = _time_score(sleep_time)

    base = 0.30 * caf_score + 0.30 * scr_score + 0.25 * act_score + 0.15 * time_score

    if caf_time and sleep_time:
        hrs = caffeine_hours_before_sleep(caf_time, sleep_time)
        if hrs is not None and hrs >= 6:
            base = min(1.0, base + 0.1)
        elif hrs is not None and hrs < 3:
            base = max(0.0, base - 0.1)
    return base


def daily_sqi(row, target_sleep):
    """
    row — кортеж из get_checkins_for_analysis:
    0 sleep, 1 quality, 2 mood, 3 energy, 4 stress,
    5 caffeine, 6 caffeine_time, 7 screen, 8 activity,
    9 nap_taken, 10 nap_duration, 11 sleep_time, 12 shift_type, 13 study_load
    """
    if not row or row[0] is None:
        return None
    sleep = float(row[0])
    q = row[1] or 3
    mood = row[2] or 3
    energy = row[3] or 3
    stress = row[4]
    if stress is None:
        stress = 3

    sleep_c = _sleep_target_score(sleep, target_sleep)
    qual_c = q / 5
    mood_c = mood / 5
    energy_c = energy / 5
    stress_c = (5 - stress) / 4
    habits_c = _habits_score(row)

    return 100 * (
        0.30 * sleep_c +
        0.20 * qual_c +
        0.15 * energy_c +
        0.10 * mood_c +
        0.10 * stress_c +
        0.15 * habits_c
    )


def rolling_sqi(rows, target_sleep, window=7):
    """Возвращает список (дата, SQI) скользящего среднего за window дней."""
    scores = [daily_sqi(r, target_sleep) for r in rows]
    result = []
    for i in range(len(scores)):
        if scores[i] is None:
            continue
        start = max(0, i - window + 1)
        window_vals = [s for s in scores[start:i + 1] if s is not None]
        if len(window_vals) < 3:
            continue
        result.append((i, mean(window_vals)))
    return result


def compute_improvement(rows, target_sleep):
    """
    Возвращает dict с процентами улучшения и деталями.
    """
    if len(rows) < 7:
        return None

    rolling = rolling_sqi(rows, target_sleep)
    if len(rolling) < 7:
        return None

    first_idx, first_val = rolling[0]
    last_idx, last_val = rolling[-1]

    # «Первый период» — первые 7 дней с данными
    first_7 = [s for _, s in rolling[:7]]
    last_7 = [s for _, s in rolling[-7:]]
    if len(first_7) < 3 or len(last_7) < 3:
        return None

    start_sqi = mean(first_7)
    end_sqi = mean(last_7)
    delta_pct = (end_sqi - start_sqi) / max(start_sqi, 1) * 100

    # Прирост по привычкам
    first_hab = mean(_habits_score(r) for r in rows[:7] if r[0] is not None)
    last_hab = mean(_habits_score(r) for r in rows[-7:] if r[0] is not None)
    habits_pct = (last_hab - first_hab) / max(first_hab, 1e-6) * 100

    return {
        "start_sqi": round(start_sqi, 1),
        "end_sqi": round(end_sqi, 1),
        "delta_pct": round(delta_pct, 1),
        "habits_pct": round(habits_pct, 1),
        "days": len(rows),
        "rolling": rolling,
    }
def _habits_score(row):
    caf = caffeine_to_number(row[5]) if len(row) > 5 else 0
    scr = screen_to_number(row[7]) if len(row) > 7 else 0
    act = activity_to_number(row[8]) if len(row) > 8 else 0
    sleep_time = row[11] if len(row) > 11 else None
    caf_time = row[6] if len(row) > 6 else None

    caf_score = 1 - caf / 3
    scr_score = 1 - scr / 3
    act_score = act / 3
    time_score = _time_score(sleep_time)

    base = (
        0.28 * caf_score
        + 0.28 * scr_score
        + 0.25 * act_score
        + 0.19 * time_score
    )

    if caf_time and sleep_time:
        hrs = caffeine_hours_before_sleep(caf_time, sleep_time)
        if hrs is not None:
            if hrs >= 6:
                base = min(1.0, base + 0.10)
            elif hrs < 3:
                base = max(0.0, base - 0.10)
    return base