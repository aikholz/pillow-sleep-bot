from collections import Counter
from datetime import datetime
from statistics import median
from math import ceil


# =========================================================
# ВОЗРАСТНОЙ ОРИЕНТИР
# =========================================================

def get_age_sleep_baseline(age: int):
    """
    Возвращает стартовый ориентир сна по возрасту.
    """

    if 10 <= age <= 12:
        return {
            "min_sleep": 9.0,
            "max_sleep": 12.0,
            "target_sleep": 10.0,
            "label": "дети 6–12 лет",
        }

    if 13 <= age <= 17:
        return {
            "min_sleep": 8.0,
            "max_sleep": 10.0,
            "target_sleep": 9.0,
            "label": "подростки 13–17 лет",
        }

    if 18 <= age <= 60:
        return {
            "min_sleep": 7.0,
            "max_sleep": None,
            "target_sleep": 8.0,
            "label": "взрослые 18–60 лет",
        }

    if 61 <= age <= 64:
        return {
            "min_sleep": 7.0,
            "max_sleep": 9.0,
            "target_sleep": 8.0,
            "label": "взрослые 61–64 лет",
        }

    if age >= 65:
        return {
            "min_sleep": 7.0,
            "max_sleep": 8.0,
            "target_sleep": 7.5,
            "label": "взрослые 65+",
        }

    return {
        "min_sleep": 7.0,
        "max_sleep": None,
        "target_sleep": 8.0,
        "label": "общий ориентир",
    }


# =========================================================
# ИНДЕКС ВОССТАНОВЛЕНИЯ
# =========================================================

def recovery_score(quality, mood, energy, stress):
    values = []
    weights = []

    if quality is not None:
        values.append(quality / 5)
        weights.append(0.40)

    if energy is not None:
        values.append(energy / 5)
        weights.append(0.30)

    if mood is not None:
        values.append(mood / 5)
        weights.append(0.20)

    if stress is not None:
        stress_score = (5 - stress) / 4
        values.append(stress_score)
        weights.append(0.10)

    if not values:
        return None

    total_weight = sum(weights)

    return sum(
        value * weight for value, weight in zip(values, weights)
    ) / total_weight


# =========================================================
# ПЕРЕВОДЫ ЗНАЧЕНИЙ
# =========================================================

def caffeine_to_number(value):
    return {
        "Не пил(а)": 0,
        "1 чашка": 1,
        "2 чашки": 2,
        "3 и более": 3,
    }.get(value, 0)


def screen_to_number(value):
    return {
        "Не смотрел(а)": 0,
        "До 30 минут": 1,
        "30–60 минут": 2,
        "Больше часа": 3,
    }.get(value, 0)


def activity_to_number(value):
    return {
        "Не было": 0,
        "Лёгкая": 1,
        "Средняя": 2,
        "Высокая": 3,
    }.get(value, 0)


def nap_to_number(value):
    return {
        None: 0,
        "До 30 минут": 0.5,
        "30–60 минут": 1,
        "Больше часа": 1.5,
    }.get(value, 0)


def time_to_minutes(value):
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%H:%M")
        return dt.hour * 60 + dt.minute
    except ValueError:
        return None


def caffeine_hours_before_sleep(caffeine_time, sleep_time):
    caffeine_minutes = time_to_minutes(caffeine_time)
    sleep_minutes = time_to_minutes(sleep_time)

    if caffeine_minutes is None or sleep_minutes is None:
        return None

    return ((sleep_minutes - caffeine_minutes) % 1440) / 60


# =========================================================
# ПЕРСОНАЛЬНАЯ ПРОДОЛЖИТЕЛЬНОСТЬ СНА
# =========================================================

def build_sleep_profile(rows, age, schedule=None):
    baseline = get_age_sleep_baseline(age)

    total_sleep_mode = (
        schedule is not None
        and ("Сменный" in schedule or "Ночной" in schedule)
    )

    observations = []

    for row in rows:
        if len(row) < 5:
            continue

        sleep = row[0]
        quality = row[1]
        mood = row[2]
        energy = row[3]
        stress = row[4]

        if sleep is None:
            continue

        effective_sleep = float(sleep)

        if total_sleep_mode and len(row) >= 11:
            nap_taken = row[9]
            nap_duration = row[10]
            if nap_taken:
                effective_sleep += nap_to_number(nap_duration)

        score = recovery_score(quality, mood, energy, stress)
        if score is None:
            continue

        observations.append({
            "sleep": effective_sleep,
            "score": score,
        })

    count = len(observations)

    if count < 14:
        return {
            "mode": "baseline",
            "days": count,
            "baseline_min": baseline["min_sleep"],
            "baseline_max": baseline["max_sleep"],
            "baseline_target": baseline["target_sleep"],
            "personal_target": baseline["target_sleep"],
            "best_observed": None,
            "zone_low": None,
            "zone_high": None,
            "zone_count": 0,
            "confidence": "низкая",
            "total_sleep_mode": total_sleep_mode,
        }

    observations.sort(key=lambda item: item["score"], reverse=True)

    top_count = max(3, ceil(count * 0.25))
    best_observations = observations[:top_count]
    best_durations = [item["sleep"] for item in best_observations]
    best_observed = median(best_durations)

    zone_low = round(best_observed - 0.5, 1)
    zone_high = round(best_observed + 0.5, 1)

    zone_observations = [
        item for item in observations
        if abs(item["sleep"] - best_observed) <= 0.5
    ]
    zone_count = len(zone_observations)

    zone_score = (
        sum(item["score"] for item in zone_observations) / zone_count
        if zone_count else None
    )

    overall_score = (
        sum(item["score"] for item in observations) / len(observations)
    )

    strong_personal_signal = (
        zone_count >= 4
        and zone_score is not None
        and zone_score >= overall_score + 0.05
    )

    if count < 28:
        personal_target = (
            baseline["target_sleep"] * 0.5 + best_observed * 0.5
        )
        confidence = (
            "средняя" if strong_personal_signal else "предварительная"
        )
        mode = "preliminary"
    else:
        if strong_personal_signal:
            personal_target = best_observed
            confidence = "хорошая"
            mode = "personal"
        else:
            personal_target = (
                baseline["target_sleep"] * 0.4 + best_observed * 0.6
            )
            confidence = "средняя"
            mode = "personal_preliminary"

    recommended_target = max(personal_target, baseline["min_sleep"])
    recommended_target = round(recommended_target * 2) / 2

    return {
        "mode": mode,
        "days": count,
        "baseline_min": baseline["min_sleep"],
        "baseline_max": baseline["max_sleep"],
        "baseline_target": baseline["target_sleep"],
        "personal_target": recommended_target,
        "best_observed": round(best_observed, 1),
        "zone_low": max(0, round(zone_low, 1)),
        "zone_high": round(zone_high, 1),
        "zone_count": zone_count,
        "zone_score": zone_score,
        "overall_score": overall_score,
        "confidence": confidence,
        "total_sleep_mode": total_sleep_mode,
    }


# =========================================================
# САМЫЕ УДАЧНЫЕ ДНИ
# =========================================================

def build_best_conditions(rows):

    observations = []

    for row in rows:
        if len(row) < 13:
            continue

        (
            sleep,
            quality,
            mood,
            energy,
            stress,
            caffeine,
            caffeine_time,
            screen_time,
            physical_activity,
            nap_taken,
            nap_duration,
            sleep_time,
            shift_type,
        ) = row

        if sleep is None:
            continue

        score = recovery_score(quality, mood, energy, stress)
        if score is None:
            continue

        observations.append({
            "sleep": float(sleep),
            "score": score,
            "quality": quality,
            "mood": mood,
            "energy": energy,
            "stress": stress,
            "caffeine": caffeine_to_number(caffeine),
            "caffeine_time": caffeine_time,
            "caffeine_before_sleep": (
                caffeine_hours_before_sleep(caffeine_time, sleep_time)
            ),
            "screen": screen_to_number(screen_time),
            "screen_text": screen_time,
            "activity": activity_to_number(physical_activity),
            "activity_text": physical_activity,
            "nap": nap_to_number(nap_duration),
            "nap_text": nap_duration,
            "nap_taken": nap_taken,
        })

    count = len(observations)

    if count < 14:
        return {"ready": False, "days": count}

    observations.sort(key=lambda item: item["score"], reverse=True)

    top_count = max(3, ceil(count * 0.25))
    best = observations[:top_count]

    def most_common(values):
        values = [v for v in values if v is not None]
        if not values:
            return None
        return Counter(values).most_common(1)[0][0]

    avg_sleep = median(item["sleep"] for item in best)
    avg_quality = median(item["quality"] for item in best if item["quality"] is not None)
    avg_energy = median(item["energy"] for item in best if item["energy"] is not None)
    avg_mood = median(item["mood"] for item in best if item["mood"] is not None)
    avg_stress = median(item["stress"] for item in best if item["stress"] is not None)
    avg_caffeine = median(item["caffeine"] for item in best)

    caffeine_timing = [
        item["caffeine_before_sleep"] for item in best
        if item["caffeine_before_sleep"] is not None
    ]
    avg_caffeine_timing = median(caffeine_timing) if caffeine_timing else None

    common_screen = most_common(item["screen_text"] for item in best)
    common_activity = most_common(item["activity_text"] for item in best)
    common_nap = most_common(item["nap_text"] for item in best)

    nap_days = sum(1 for item in best if item["nap_taken"])

    return {
        "ready": True,
        "days": count,
        "best_days": top_count,
        "sleep": round(avg_sleep, 1),
        "quality": round(avg_quality, 1),
        "energy": round(avg_energy, 1),
        "mood": round(avg_mood, 1),
        "stress": round(avg_stress, 1) if avg_stress is not None else None,
        "caffeine": round(avg_caffeine, 1),
        "caffeine_timing": (
            round(avg_caffeine_timing, 1)
            if avg_caffeine_timing is not None else None
        ),
        "screen": common_screen,
        "activity": common_activity,
        "nap": common_nap,
        "nap_days": nap_days,
    }


# =========================================================
# ТЕКСТ ПЕРСОНАЛЬНОГО ПРОФИЛЯ
# =========================================================

def format_sleep_profile(profile):

    if profile["mode"] == "baseline":
        return (
            "🧭 ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ ПОКА НЕ ГОТОВ\n\n"
            f"Пока ориентир — около "
            f"{profile['baseline_target']:.1f} ч "
            "(среднестатистическая норма для твоего возраста).\n\n"
            "По мере накопления данных «Подушка» начнёт "
            "определять твой индивидуальный диапазон."
        )

    if profile["mode"] == "preliminary":
        return (
            "🧭 ПРЕДВАРИТЕЛЬНЫЙ ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ\n\n"
            f"Твой текущий ориентир сна — около "
            f"{profile['personal_target']:.1f} ч.\n\n"
            "Это предварительная оценка — "
            "она будет уточняться по мере накопления "
            "новых данных."
        )

    if profile["mode"] == "personal":
        return (
            "🎯 ТВОЙ ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ СНА\n\n"
            f"Спать лучше всего в диапазоне "
            f"{profile['zone_low']:.1f}–"
            f"{profile['zone_high']:.1f} ч "
            f"(центр — {profile['personal_target']:.1f} ч).\n\n"
            f"Дней наблюдения: {profile['days']}\n"
            f"Достоверность паттерна: {profile['confidence']}.\n\n"
            "Это значит, что при сне в этом диапазоне "
            "ты в среднем чувствуешь себя лучше всего."
        )

    return (
        "🧭 Персональный профиль уже рассчитывается.\n\n"
        f"Текущий ориентир: {profile['personal_target']:.1f} ч."
    )


# =========================================================
# ТЕКСТ ЛУЧШИХ УСЛОВИЙ
# =========================================================

def format_best_conditions(profile):

    if not profile["ready"]:
        return (
            "🔬 Чтобы найти твои лучшие дни, "
            "нужно минимум 14 дней данных.\n\n"
            f"Сейчас накоплено: {profile['days']} дней."
        )

    text = (
        "🔬 ТВОИ ЛУЧШИЕ ДНИ\n\n"
        f"Мы проанализировали {profile['best_days']} твоих "
        f"лучших дней из {profile['days']}.\n\n"
        "В эти дни у тебя обычно:\n"
        f"😴 Сон: {profile['sleep']:.1f} ч\n"
        f"⭐ Качество: {profile['quality']:.1f}/5\n"
        f"🙂 Настроение: {profile['mood']:.1f}/5\n"
        f"⚡ Энергия: {profile['energy']:.1f}/5\n"
    )

    if profile["stress"] is not None:
        text += f"😰 Стресс: {profile['stress']:.1f}/5\n"

    text += f"☕ Кофеин: {profile['caffeine']:.1f} порций\n"

    if profile["caffeine_timing"] is not None:
        text += (
            f"⏰ Кофеин за {profile['caffeine_timing']:.1f} ч до сна\n"
        )

    if profile["screen"] is not None:
        text += f"📱 Экран: {profile['screen']}\n"

    if profile["activity"] is not None:
        text += f"🏃 Активность: {profile['activity']}\n"

    if profile["nap"] is not None:
        text += f"🌙 Дневной сон: {profile['nap']}\n"

    text += (
        "\n📌 Это портрет твоих хороших дней, а не рецепт. "
        "Но если ты замечаешь, что в эти дни повторяется "
        "одно и то же — это может быть твоя закономерность."
    )

    return text


# =========================================================
# ЦИРКАДНЫЙ АНАЛИЗ
# =========================================================

def _time_to_minutes(value):
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%H:%M")
        return dt.hour * 60 + dt.minute
    except ValueError:
        return None


def _format_time_from_minutes(minutes):
    if minutes is None:
        return None
    minutes = int(minutes) % (24 * 60)
    hh = minutes // 60
    mm = minutes % 60
    return f"{hh:02d}:{mm:02d}"


def analyze_circadian(rows):
    """
    Улучшенный циркадный анализ.
    Считает медианное время сна и подъема для будней и выходных.
    """
    from statistics import median

    weekday_sleeps = []
    weekend_sleeps = []
    weekday_wakes = []
    weekend_wakes = []

    for row in rows:
        if len(row) < 13:
            continue

        checkin_date = row[0]
        sleep_time = row[11]
        wake_time = row[12]

        sleep_min = _time_to_minutes(sleep_time)
        wake_min = _time_to_minutes(wake_time)

        if sleep_min is None or wake_min is None:
            continue

        # Корректировка на переход через полночь
        if sleep_min < 12 * 60:
            sleep_min += 24 * 60
        if wake_min < sleep_min - 12 * 60:
            wake_min += 24 * 60

        weekday = checkin_date.weekday()

        if weekday < 5:
            weekday_sleeps.append(sleep_min)
            weekday_wakes.append(wake_min)
        else:
            weekend_sleeps.append(sleep_min)
            weekend_wakes.append(wake_min)

    if not weekday_sleeps or not weekend_sleeps:
        return None

    # Используем медиану вместо среднего, чтобы выбросы не искажали картину
    avg_wd_sleep = median(weekday_sleeps)
    avg_we_sleep = median(weekend_sleeps)
    avg_wd_wake = median(weekday_wakes)
    avg_we_wake = median(weekend_wakes)

    mid_wd = (avg_wd_sleep + avg_wd_wake) / 2
    mid_we = (avg_we_sleep + avg_we_wake) / 2
    social_jetlag_min = abs(mid_we - mid_wd)

    all_sleeps = weekday_sleeps + weekend_sleeps
    mean_all = sum(all_sleeps) / len(all_sleeps)
    variance = sum((x - mean_all) ** 2 for x in all_sleeps) / len(all_sleeps)
    std_dev_min = variance ** 0.5

    return {
        "weekday_sleep": avg_wd_sleep / 60,
        "weekend_sleep": avg_we_sleep / 60,
        "weekday_wake": avg_wd_wake / 60,
        "weekend_wake": avg_we_wake / 60,
        "sleep_shift_min": avg_we_sleep - avg_wd_sleep,
        "wake_shift_min": avg_we_wake - avg_wd_wake,
        "social_jetlag_hours": social_jetlag_min / 60,
        "std_dev_hours": std_dev_min / 60,
        "weekday_count": len(weekday_sleeps),
        "weekend_count": len(weekend_sleeps),
    }

def build_circadian_insights(circ):
    if not circ:
        return None

    lines = []

    sleep_shift = circ["sleep_shift_min"]
    wake_shift = circ["wake_shift_min"]

    if abs(sleep_shift) >= 30:
        lines.append(
            f"🛌 В выходные ты ложишься спать в среднем "
            f"в {_format_time_from_minutes(circ['weekend_sleep'] * 60)} "
            f"вместо {_format_time_from_minutes(circ['weekday_sleep'] * 60)} "
            f"в рабочие дни."
        )

    if abs(wake_shift) >= 30:
        lines.append(
            f"☀️ Встаёшь в выходные в "
            f"{_format_time_from_minutes(circ['weekend_wake'] * 60)} "
            f"вместо {_format_time_from_minutes(circ['weekday_wake'] * 60)}."
        )

    sj = circ["social_jetlag_hours"]

    if sj >= 2:
        lines.append(
            f"⚠️ Социальный джетлаг: {sj:.1f} ч. "
            "Это заметный сдвиг режима на выходных. "
            "В понедельник утром он может ощущаться "
            "как «мини-джетлаг»."
        )
    elif sj >= 1:
        lines.append(
            f"📊 Социальный джетлаг: {sj:.1f} ч. "
            "Умеренный сдвиг — старайся не сдвигать "
            "режим больше, чем на час."
        )

    std = circ["std_dev_hours"]

    if std < 0.5:
        lines.append(
            f"✅ Время сна стабильное (разброс ~{std*60:.0f} мин). "
            "Это хорошо для циркадных ритмов."
        )
    elif std < 1.0:
        lines.append(
            f"📊 Время сна колеблется в пределах ~{std:.1f} ч. "
            "Это умеренный разброс."
        )
    else:
        lines.append(
            f"⚠️ Время сна сильно «плавает» "
            f"(разброс ~{std:.1f} ч). "
            "Это может влиять на качество сна "
            "и утреннее самочувствие."
        )

    if not lines:
        return None

    return "\n".join(lines)