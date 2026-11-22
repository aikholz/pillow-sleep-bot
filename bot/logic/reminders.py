# bot/logic/reminders.py
"""
База советов и контекстный подбор.
Советы подбираются по контексту (build_context) и отдаются по приоритету.
"""

TIPS = [
    {
        "id": "coffee_early",
        "text": "Перенеси последнюю чашку кофе на 6+ часов до сна — это на 20–30% ускоряет засыпание.",
        "condition": lambda ctx: ctx.get("late_coffee_days", 0) >= 2,
        "priority": 3,
    },
    {
        "id": "screen_off",
        "text": "Убери экран за час до сна: синий свет подавляет мелатонин почти в 2 раза.",
        "condition": lambda ctx: ctx.get("high_screen_days", 0) >= 2,
        "priority": 3,
    },
    {
        "id": "walk",
        "text": "Добавь 20-минутную прогулку днём — она улучшает глубокий сон на 15%.",
        "condition": lambda ctx: ctx.get("low_activity_days", 0) >= 3,
        "priority": 2,
    },
    {
        "id": "stress_breath",
        "text": "Перед сном попробуй 5 минут дыхания 4-7-8: вдох 4, задержка 7, выдох 8.",
        "condition": lambda ctx: ctx.get("high_stress_days", 0) >= 2,
        "priority": 3,
    },
    {
        "id": "early_bed",
        "text": "Сдвинь отход ко сну на 30 минут раньше — SQI растёт в среднем на 5 пунктов.",
        "condition": lambda ctx: ctx.get("late_sleep_days", 0) >= 2,
        "priority": 2,
    },
    {
        "id": "consistency",
        "text": "Стабильное время подъёма (даже в выходные) стабилизирует циркадные ритмы лучше, чем раннее засыпание.",
        "condition": lambda ctx: ctx.get("social_jetlag", 0) >= 1.5,
        "priority": 3,
    },
    {
        "id": "nap_short",
        "text": "Дневной сон длиннее 30 минут может «съедать» ночной сон — ограничь его 20–30 минутами.",
        "condition": lambda ctx: ctx.get("long_naps", 0) >= 2,
        "priority": 2,
    },
    {
        "id": "room_temp",
        "text": "Снизь температуру в спальне до 18–20°C — это ускоряет засыпание на 10 минут.",
        "condition": lambda ctx: ctx.get("low_quality_days", 0) >= 3,
        "priority": 1,
    },
    {
        "id": "eat_early",
        "text": "Не ешь плотно за 2–3 часа до сна — это уменьшит ночные пробуждения.",
        "condition": lambda ctx: ctx.get("low_quality_days", 0) >= 2,
        "priority": 1,
    },
    {
        "id": "shift_light",
        "text": "После ночной смены сразу надевай тёмные очки и не включай яркий свет дома — быстрее уснёшь.",
        "condition": lambda ctx: ctx.get("night_shift_days", 0) >= 2,
        "priority": 3,
    },
    {
        "id": "student_breaks",
        "text": "При интенсивной учёбе ставь Pomodoro 50/10 — перерывы снижают вечерний стресс и улучшают сон.",
        "condition": lambda ctx: ctx.get("study_heavy_days", 0) >= 2,
        "priority": 2,
    },
    {
        "id": "weekend_anchor",
        "text": "Ставь будильник на выходные не позже +1 часа от будней — так понедельники не будут «тяжёлыми».",
        "condition": lambda ctx: ctx.get("social_jetlag", 0) >= 1.0,
        "priority": 2,
    },
    # --- График: сменный / ночной ---
    {
        "id": "shift_light_morning",
        "text": "После утренней смены сразу выходи на яркий свет 10–15 мин — это «перезагружает» циркадный ритм.",
        "condition": lambda ctx: ctx.get("is_shift") and ctx.get("morning_shift_days", 0) >= 2,
        "priority": 3,
    },
    {
        "id": "shift_meal",
        "text": "Старайся есть в одно и то же время при сменном графике — это стабилизирует внутренние часы.",
        "condition": lambda ctx: ctx.get("is_shift") and ctx.get("social_jetlag", 0) >= 1.0,
        "priority": 2,
    },
    {
        "id": "night_dark_room",
        "text": "При ночных сменах спи днём в полной темноте (блэкаут-шторы или маска) — так сон будет глубже.",
        "condition": lambda ctx: ctx.get("is_night"),
        "priority": 3,
    },
    {
        "id": "night_no_alcohol",
        "text": "После ночной смены не пей алкоголь «для расслабления» — он разрушает глубокий сон.",
        "condition": lambda ctx: ctx.get("is_night") and ctx.get("low_quality_days", 0) >= 2,
        "priority": 2,
    },
    {
        "id": "nap_counted",
        "text": "При ночном графике дневной сон 20–40 мин — часть восстановления, а не «лишний». Считай его в сутки.",
        "condition": lambda ctx: ctx.get("total_sleep_mode"),
        "priority": 3,
    },
    # --- Учёба ---
    {
        "id": "student_exam",
        "text": "В сессию ставь сон в приоритет над «доделать всё ночью»: недосып в 2 ч снижает запоминание на 40%.",
        "condition": lambda ctx: ctx.get("is_student") and ctx.get("study_heavy_days", 0) >= 2,
        "priority": 3,
    },
    {
        "id": "student_no_allnighter",
        "text": "Одна бессонная ночь перед экзаменом даёт меньше, чем 7 часов сна — память работает во сне.",
        "condition": lambda ctx: ctx.get("is_student") and ctx.get("late_sleep_days", 0) >= 2,
        "priority": 2,
    },
    # --- Офис ---
    {
        "id": "office_daylight",
        "text": "В обед выходи на улицу хотя бы на 10 минут — дневной свет улучшает ночной сон.",
        "condition": lambda ctx: ctx.get("is_office") and ctx.get("low_activity_days", 0) >= 2,
        "priority": 2,
    },
    {
        "id": "office_screen_cut",
        "text": "За час до сна — режим «Не беспокоить». Уведомления мешают засыпанию сильнее, чем сам экран.",
        "condition": lambda ctx: ctx.get("is_office") and ctx.get("high_screen_days", 0) >= 2,
        "priority": 3,
    },
    # --- Физический труд ---
    {
        "id": "physical_stretch",
        "text": "После тяжёлой физической работы 10 минут растяжки снижают мышечное напряжение и помогают уснуть.",
        "condition": lambda ctx: ctx.get("is_physical"),
        "priority": 2,
    },
    {
        "id": "physical_hydration",
        "text": "Пей воду в течение дня, но ограничь за 2 часа до сна — меньше ночных пробуждений.",
        "condition": lambda ctx: ctx.get("is_physical") and ctx.get("low_quality_days", 0) >= 2,
        "priority": 1,
    },
    # --- Фриланс / свободный график ---
    {
        "id": "freelance_anchor",
        "text": "При свободном графике задай «якорь» — одно и то же время подъёма. Это удержит ритм.",
        "condition": lambda ctx: ctx.get("is_freelance") and ctx.get("social_jetlag", 0) >= 1.0,
        "priority": 3,
    },
    {
        "id": "freelance_no_work_in_bed",
        "text": "Не работай в кровати — мозг начнёт связывать её с работой, а не со сном.",
        "condition": lambda ctx: ctx.get("is_freelance") and ctx.get("late_sleep_days", 0) >= 2,
        "priority": 2,
    },
    # --- Универсальные ---
    {
        "id": "morning_light",
        "text": "Утром открой шторы сразу после подъёма — 10 минут яркого света стабилизируют циркадный ритм.",
        "condition": lambda ctx: ctx.get("social_jetlag", 0) >= 1.5,
        "priority": 3,
    },
    {
        "id": "bed_ritual",
        "text": "Придумай 10-минутный ритуал перед сном (душ, книга, чай) — мозгу нужен сигнал «пора спать».",
        "condition": lambda ctx: ctx.get("low_quality_days", 0) >= 3,
        "priority": 2,
    },
]


def select_tips(ctx, limit=3):
    """Возвращает до limit текстов советов, отсортированных по приоритету."""
    scored = []
    for tip in TIPS:
        try:
            if tip["condition"](ctx):
                scored.append((tip["priority"], tip["text"]))
        except Exception:
            pass
    scored.sort(reverse=True, key=lambda x: x[0])
    return [t for _, t in scored[:limit]]


def build_context(telegram_id, rows):
    """Считает контекстные метрики для select_tips."""
    late_coffee = sum(1 for r in rows if r[6] and int(r[6].split(":")[0]) >= 17)
    high_screen = sum(1 for r in rows if r[7] in ("Больше часа",))
    low_act = sum(1 for r in rows if r[8] in ("Не было", "Лёгкая"))
    high_stress = sum(1 for r in rows if (r[4] or 0) >= 4)
    late_sleep = sum(1 for r in rows if r[11] and int(r[11].split(":")[0]) in (0, 1, 2))
    long_naps = sum(1 for r in rows if r[10] == "Больше часа")
    low_qual = sum(1 for r in rows if (r[1] or 5) <= 2)
    night_shifts = sum(1 for r in rows if r[12] == "Ночь")
    study_heavy = sum(1 for r in rows if len(r) > 13 and r[13] == 2)

    from bot.logic.sleep_model import analyze_circadian
    circ = analyze_circadian(rows)
    sj = circ["social_jetlag_hours"] if circ else 0

    return {
        "late_coffee_days": late_coffee,
        "high_screen_days": high_screen,
        "low_activity_days": low_act,
        "high_stress_days": high_stress,
        "late_sleep_days": late_sleep,
        "long_naps": long_naps,
        "low_quality_days": low_qual,
        "night_shift_days": night_shifts,
        "study_heavy_days": study_heavy,
        "social_jetlag": sj,
    }

    def build_context(telegram_id, rows):
        late_coffee = sum(1 for r in rows if r[6] and int(r[6].split(":")[0]) >= 17)
        high_screen = sum(1 for r in rows if r[7] == "Больше часа")
        low_act = sum(1 for r in rows if r[8] in ("Не было", "Лёгкая"))
        high_stress = sum(1 for r in rows if (r[4] or 0) >= 4)
        late_sleep = sum(1 for r in rows if r[11] and int(r[11].split(":")[0]) in (0, 1, 2))
        long_naps = sum(1 for r in rows if r[10] == "Больше часа")
        low_qual = sum(1 for r in rows if (r[1] or 5) <= 2)
        night_shifts = sum(1 for r in rows if r[12] == "Ночь")
        study_heavy = sum(1 for r in rows if len(r) > 13 and r[13] == 2)
        morning_shifts = sum(1 for r in rows if r[12] == "Утро")

        from bot.logic.sleep_model import analyze_circadian
        circ = analyze_circadian(rows)
        sj = circ["social_jetlag_hours"] if circ else 0

        return {
            "late_coffee_days": late_coffee,
            "high_screen_days": high_screen,
            "low_activity_days": low_act,
            "high_stress_days": high_stress,
            "late_sleep_days": late_sleep,
            "long_naps": long_naps,
            "low_quality_days": low_qual,
            "night_shift_days": night_shifts,
            "morning_shift_days": morning_shifts,  # новое
            "study_heavy_days": study_heavy,
            "social_jetlag": sj,
        }
def select_tips(ctx, limit=3):
    scored = []
    for tip in TIPS:
        try:
            if tip["condition"](ctx):
                scored.append((tip["priority"], tip["id"], tip["text"]))
        except Exception:
            pass
    scored.sort(reverse=True, key=lambda x: x[0])

    seen, result = set(), []
    for _, tid, text in scored:
        if tid in seen:
            continue
        seen.add(tid)
        result.append(text)
        if len(result) >= limit:
            break
    return result
