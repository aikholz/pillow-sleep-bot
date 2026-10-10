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

    Это не персональная норма пользователя.
    Это только отправная точка до накопления
    достаточного количества индивидуальных данных.
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

def recovery_score(
    quality,
    mood,
    energy,
    stress
):
    """
    Оценка того, насколько хорошо человек
    чувствовал себя после конкретной ночи.

    Качество сна       — 40%
    Энергия             — 30%
    Настроение          — 20%
    Обратный стресс     — 10%
    """

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
        value * weight
        for value, weight in zip(values, weights)
    ) / total_weight


# =========================================================
# ПЕРСОНАЛЬНАЯ ПРОДОЛЖИТЕЛЬНОСТЬ СНА
# =========================================================

def build_sleep_profile(rows, age, schedule=None):

    baseline = get_age_sleep_baseline(age)

    total_sleep_mode = (
        schedule is not None
        and (
            "Сменный" in schedule
            or "Ночной" in schedule
        )
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

        score = recovery_score(
            quality,
            mood,
            energy,
            stress
        )

        if score is None:
            continue

        observations.append({
            "sleep": effective_sleep,
            "score": score,
        })

    count = len(observations)

    # ---------------------------------------------
    # Мало данных
    # ---------------------------------------------

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

    # ---------------------------------------------
    # Сортировка от лучших дней к худшим
    # ---------------------------------------------

    observations.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    top_count = max(
        3,
        ceil(count * 0.25)
    )

    best_observations = observations[:top_count]

    best_durations = [
        item["sleep"]
        for item in best_observations
    ]

    best_observed = median(best_durations)

    zone_low = round(best_observed - 0.5, 1)
    zone_high = round(best_observed + 0.5, 1)

    zone_observations = [
        item
        for item in observations
        if abs(item["sleep"] - best_observed) <= 0.5
    ]

    zone_count = len(zone_observations)

    zone_score = (
        sum(item["score"] for item in zone_observations) / zone_count
        if zone_count
        else None
    )

    overall_score = (
        sum(item["score"] for item in observations) / len(observations)
    )

    strong_personal_signal = (
        zone_count >= 4
        and zone_score is not None
        and zone_score >= overall_score + 0.05
    )

    # ---------------------------------------------
    # До 28 дней
    # ---------------------------------------------

    if count < 28:

        personal_target = (
            baseline["target_sleep"] * 0.5
            + best_observed * 0.5
        )

        confidence = (
            "средняя"
            if strong_personal_signal
            else "предварительная"
        )

        mode = "preliminary"

    else:

        if strong_personal_signal:

            personal_target = best_observed
            confidence = "хорошая"
            mode = "personal"

        else:

            personal_target = (
                baseline["target_sleep"] * 0.4
                + best_observed * 0.6
            )

            confidence = "средняя"
            mode = "personal_preliminary"

    recommended_target = max(
        personal_target,
        baseline["min_sleep"]
    )

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

        dt = datetime.strptime(
            value,
            "%H:%M"
        )

        return dt.hour * 60 + dt.minute

    except ValueError:

        return None


def caffeine_hours_before_sleep(
    caffeine_time,
    sleep_time
):

    caffeine_minutes = time_to_minutes(
        caffeine_time
    )

    sleep_minutes = time_to_minutes(
        sleep_time
    )

    if (
        caffeine_minutes is None
        or sleep_minutes is None
    ):
        return None

    return (
        (sleep_minutes - caffeine_minutes) % 1440
    ) / 60


# =========================================================
# САМЫЕ УДАЧНЫЕ ДНИ
# =========================================================

def build_best_conditions(rows):

    observations = []

    for row in rows:

        if len(row) < 12:
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
        ) = row

        if sleep is None:
            continue

        score = recovery_score(
            quality,
            mood,
            energy,
            stress
        )

        if score is None:
            continue

        observations.append({
            "sleep": float(sleep),
            "score": score,
            "quality": quality,
            "mood": mood,
            "energy": energy,
            "stress": stress,
            "caffeine": caffeine_to_number(
                caffeine
            ),
            "caffeine_time": caffeine_time,
            "caffeine_before_sleep": (
                caffeine_hours_before_sleep(
                    caffeine_time,
                    sleep_time
                )
            ),
            "screen": screen_to_number(
                screen_time
            ),
            "screen_text": screen_time,
            "activity": activity_to_number(
                physical_activity
            ),
            "activity_text": physical_activity,
            "nap": nap_to_number(
                nap_duration
            ),
            "nap_text": nap_duration,
            "nap_taken": nap_taken,
        })

    count = len(observations)

    if count < 14:

        return {
            "ready": False,
            "days": count,
        }

    observations.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    top_count = max(
        3,
        ceil(count * 0.25)
    )

    best = observations[:top_count]

    # ---------------------------------------------
    # Самая частая категория
    # ---------------------------------------------

    def most_common(values):

        values = [
            value
            for value in values
            if value is not None
        ]

        if not values:
            return None

        return Counter(values).most_common(1)[0][0]

    # ---------------------------------------------
    # Средние значения лучших ночей
    # ---------------------------------------------

    avg_sleep = median(
        item["sleep"]
        for item in best
    )

    avg_quality = median(
        item["quality"]
        for item in best
        if item["quality"] is not None
    )

    avg_energy = median(
        item["energy"]
        for item in best
        if item["energy"] is not None
    )

    avg_mood = median(
        item["mood"]
        for item in best
        if item["mood"] is not None
    )

    avg_stress = median(
        item["stress"]
        for item in best
        if item["stress"] is not None
    )

    avg_caffeine = median(
        item["caffeine"]
        for item in best
    )

    caffeine_timing = [
        item["caffeine_before_sleep"]
        for item in best
        if item["caffeine_before_sleep"] is not None
    ]

    avg_caffeine_timing = (
        median(caffeine_timing)
        if caffeine_timing
        else None
    )

    common_screen = most_common(
        item["screen_text"]
        for item in best
    )

    common_activity = most_common(
        item["activity_text"]
        for item in best
    )

    common_nap = most_common(
        item["nap_text"]
        for item in best
    )

    nap_days = sum(
        1
        for item in best
        if item["nap_taken"]
    )

    return {
        "ready": True,
        "days": count,
        "best_days": top_count,

        "sleep": round(
            avg_sleep,
            1
        ),

        "quality": round(
            avg_quality,
            1
        ),

        "energy": round(
            avg_energy,
            1
        ),

        "mood": round(
            avg_mood,
            1
        ),

        "stress": (
            round(avg_stress, 1)
            if avg_stress is not None
            else None
        ),

        "caffeine": round(
            avg_caffeine,
            1
        ),

        "caffeine_timing": (
            round(
                avg_caffeine_timing,
                1
            )
            if avg_caffeine_timing is not None
            else None
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
            "🧭 Пока мы ориентируемся на возрастной "
            "диапазон сна.\n"
            f"Стартовый ориентир: около "
            f"{profile['baseline_target']:.1f} ч.\n\n"
            "По мере накопления данных «Подушка» "
            "начнёт определять твой индивидуальный "
            "диапазон."
        )

    if profile["mode"] == "preliminary":

        return (
            "🧭 ПРЕДВАРИТЕЛЬНЫЙ ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ\n\n"
            f"Лучшие наблюдаемые результаты были около "
            f"{profile['best_observed']:.1f} ч сна.\n"
            f"Текущий ориентир: "
            f"{profile['personal_target']:.1f} ч.\n\n"
            "Это предварительная оценка. "
            "Она будет уточняться по мере накопления "
            "новых данных."
        )

    if profile["mode"] == "personal":

        return (
            "🎯 ТВОЙ ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ СНА\n\n"
            f"Лучшие наблюдаемые результаты: "
            f"{profile['best_observed']:.1f} ч\n"
            f"Рабочая зона: "
            f"{profile['zone_low']:.1f}–"
            f"{profile['zone_high']:.1f} ч\n"
            f"Персональный ориентир: "
            f"{profile['personal_target']:.1f} ч\n"
            f"Дней наблюдения: "
            f"{profile['days']}\n"
            f"Достоверность паттерна: "
            f"{profile['confidence']}."
        )

    return (
        "🧭 Персональный профиль уже рассчитывается.\n\n"
        f"Текущий ориентир: "
        f"{profile['personal_target']:.1f} ч."
    )


# =========================================================
# ТЕКСТ ЛУЧШИХ УСЛОВИЙ
# =========================================================

def format_best_conditions(profile):

    if not profile["ready"]:

        return (
            "🔬 Для поиска твоего лучшего набора "
            "условий нужно минимум 14 дней данных.\n\n"
            f"Сейчас накоплено: "
            f"{profile['days']} дней."
        )

    text = (
        "🔬 УСЛОВИЯ ЛУЧШИХ ДНЕЙ\n\n"
        f"Мы посмотрели {profile['best_days']} лучших "
        f"наблюдений из {profile['days']} дней.\n\n"
        f"😴 Сон: около {profile['sleep']:.1f} ч\n"
        f"⭐ Качество: {profile['quality']:.1f}/5\n"
        f"🙂 Настроение: {profile['mood']:.1f}/5\n"
        f"⚡ Энергия: {profile['energy']:.1f}/5\n"
    )

    if profile["stress"] is not None:

        text += (
            f"😰 Стресс: {profile['stress']:.1f}/5\n"
        )

    text += (
        f"☕ Кофеин: около "
        f"{profile['caffeine']:.1f} порций\n"
    )

    if profile["caffeine_timing"] is not None:

        text += (
            f"⏰ До сна после последнего кофеина: "
            f"около {profile['caffeine_timing']:.1f} ч\n"
        )

    if profile["screen"] is not None:

        text += (
            f"📱 Экран перед сном: "
            f"{profile['screen']}\n"
        )

    if profile["activity"] is not None:

        text += (
            f"🏃 Активность: "
            f"{profile['activity']}\n"
        )

    if profile["nap"] is not None:

        text += (
            f"🌙 Дневной сон: "
            f"{profile['nap']}\n"
        )

    text += (
        "\n📌 Это описание твоих лучших наблюдаемых "
        "дней, а не доказательство того, что именно "
        "эти факторы являются причиной хорошего сна."
    )

    return text