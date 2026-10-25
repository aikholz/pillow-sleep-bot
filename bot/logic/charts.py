import os
import tempfile
import numpy as np

import matplotlib

matplotlib.use("Agg")  # без GUI для сервера

import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.lines import Line2D
import matplotlib.dates as mdates

# Настройки для красивого отображения кириллицы
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = "#CCCCCC"
plt.rcParams["axes.linewidth"] = 1.2


# ============================================================
# ВСПОМОГАТЕЛЬНОЕ: сохранение PNG
# ============================================================

def _save_to_tempfile(fig):
    """Сохраняет фигуру во временный PNG и возвращает путь."""
    tmp = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
        dir=tempfile.gettempdir(),
    )
    fig.savefig(
        tmp.name,
        dpi=130,
        bbox_inches="tight",
        transparent=False,
        facecolor="white"
    )
    plt.close(fig)
    tmp.close()
    return tmp.name


# ============================================================
# ГРАФИК 1. Сон по дням (линейный)
# ============================================================

def make_sleep_by_day_chart(rows):
    """
    rows — из get_checkins_for_period.
        row[0] — checkin_date
        row[1] — sleep_duration
    """
    dates = []
    sleeps = []

    for row in rows:
        if len(row) >= 2 and row[0] is not None and row[1] is not None:
            dates.append(row[0])
            sleeps.append(float(row[1]))

    if not dates:
        return None

    fig, ax = plt.subplots(figsize=(8, 4.5))

    # Линия с точками
    ax.plot(dates, sleeps, marker="o", color="#3B82F6", linewidth=2, markersize=6, zorder=3)

    # Заливка под линией
    ax.fill_between(dates, sleeps, alpha=0.1, color="#3B82F6")

    # Линия среднего
    avg = sum(sleeps) / len(sleeps)
    ax.axhline(avg, color="#EF4444", linestyle="--", linewidth=1.5, label=f"Среднее: {avg:.1f} ч", zorder=2)

    ax.set_title("Сон по дням", fontsize=15, fontweight='bold', pad=15, color="#1F2937")
    ax.set_ylabel("Часы", fontsize=11)
    ax.grid(True, axis="y", linestyle="-", alpha=0.1)

    # Красивые даты
    ax.xaxis.set_major_formatter(DateFormatter("%d.%m"))
    # Чтобы даты не наезжали друг на друга
    if len(dates) > 7:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 7)))

    fig.autofmt_xdate()

    # Убираем верхнюю и правую рамки
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    ax.legend(frameon=False, loc='lower right')

    return _save_to_tempfile(fig)


# ============================================================
# ГРАФИК 2. Средний сон по типам смен (столбцы)
# ============================================================

def make_shift_chart(shift_stats):
    """
    shift_stats — результат analyze_by_shift_type(rows).
    Строит столбцы по каждому типу смены.
    """
    if not shift_stats:
        return None

    valid = {
        k: v for k, v in shift_stats.items()
        if v.get("avg_sleep") is not None
    }

    if len(valid) < 2:
        return None

    # Сортируем по значению сна
    items = sorted(valid.items(), key=lambda x: x[1]["avg_sleep"])

    labels = [k for k, _ in items]
    values = [v["avg_sleep"] for _, v in items]

    colors = ["#F87171", "#FBBF24", "#34D399", "#60A5FA", "#A78BFA"][:len(items)]

    fig, ax = plt.subplots(figsize=(7, 4.5))

    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=3)

    # Подписи значений над столбцами
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            f"{val:.1f} ч",
            ha="center", va="bottom",
            fontsize=12, fontweight="bold", color="#374151",
        )

    # Средняя линия
    avg = sum(values) / len(values)
    ax.axhline(avg, color="#9CA3AF", linestyle="--", linewidth=1.5, label=f"Среднее: {avg:.1f} ч", zorder=2)

    ax.set_title("Средний сон по сменам", fontsize=15, fontweight='bold', pad=15, color="#1F2937")
    ax.set_ylabel("Часы", fontsize=11)
    ax.set_ylim(0, max(values) + 1.5)
    ax.grid(True, axis="y", linestyle="-", alpha=0.1)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    ax.legend(frameon=False)

    return _save_to_tempfile(fig)


# ============================================================
# ГРАФИК 3. Циркадный ритм (сжатый и читабельный)
# ============================================================

def make_circadian_chart(circ):
    if not circ:
        return None

    fig, ax = plt.subplots(figsize=(8, 4.5))

    # Нормализуем время
    wd_sleep = circ["weekday_sleep"] % 24
    we_sleep = circ["weekend_sleep"] % 24
    wd_wake = circ["weekday_wake"] % 24
    we_wake = circ["weekend_wake"] % 24

    # Сдвиг для отрисовки (если время меньше 12:00, добавляем 24)
    def _shift(h):
        return h + 24 if h < 12 else h

    # Точки
    ax.scatter([_shift(wd_sleep), _shift(we_sleep)], [1, 2], s=150, color=["#3B82F6", "#F87171"], zorder=4)
    ax.scatter([_shift(wd_wake), _shift(we_wake)], [1, 2], s=150, color=["#10B981", "#F59E0B"], marker="^", zorder=4)

    # Линии длительности сна
    if wd_sleep > wd_wake:
        ax.plot([_shift(wd_sleep), 36], [1, 1], color="#3B82F6", linewidth=6, alpha=0.2, zorder=2)
        ax.plot([24, _shift(wd_wake)], [1, 1], color="#10B981", linewidth=6, alpha=0.2, zorder=2)
    else:
        ax.plot([_shift(wd_sleep), _shift(wd_wake)], [1, 1], color="#6B7280", linewidth=6, alpha=0.2, zorder=2)

    if we_sleep > we_wake:
        ax.plot([_shift(we_sleep), 36], [2, 2], color="#F87171", linewidth=6, alpha=0.2, zorder=2)
        ax.plot([24, _shift(we_wake)], [2, 2], color="#F59E0B", linewidth=6, alpha=0.2, zorder=2)
    else:
        ax.plot([_shift(we_sleep), _shift(we_wake)], [2, 2], color="#6B7280", linewidth=6, alpha=0.2, zorder=2)

    # Ось X: от 20:00 до 12:00 следующего дня (сжали, чтобы не было пустоты)
    ax.set_xlim(20, 36)
    ticks = list(range(20, 24)) + list(range(24, 37))
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{h % 24:02d}:00" for h in ticks], rotation=45)

    # Ось Y
    ax.set_yticks([1, 2])
    ax.set_yticklabels(["Будни", "Выходные"], fontsize=12, fontweight="bold")
    ax.set_ylim(0.5, 2.5)

    # Заголовок
    ax.set_title(
        f"Циркадный ритм (сдвиг: {circ['social_jetlag_hours']:.1f} ч)",
        fontsize=15, fontweight='bold', pad=20, color="#1F2937"
    )

    # Сетка
    ax.grid(True, axis="x", linestyle="--", alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    # Легенда СНИЗУ, чтобы не перекрывать заголовок
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#3B82F6', markersize=10, label='Сон (будни)'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#F87171', markersize=10, label='Сон (вых.)'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor='#10B981', markersize=10, label='Подъем (будни)'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor='#F59E0B', markersize=10, label='Подъем (вых.)')
    ]
    ax.legend(
        handles=legend_elements,
        loc='upper center',
        bbox_to_anchor=(0.5, -0.15),  # Сдвиг вниз под график
        ncol=4,
        frameon=False,
        fontsize=10
    )

    plt.tight_layout()
    return _save_to_tempfile(fig)


# ============================================================
# ГРАФИК 4. Учебная нагрузка (для студентов)
# ============================================================

def make_study_load_chart(rows):
    """
    Строит график: средний сон в дни с нагрузкой и без.
    rows — из get_checkins_for_analysis:
        row[0] — sleep_duration
        row[13] — study_load (0 или 1)
    """
    if not rows:
        return None

    normal_sleeps = []
    loaded_sleeps = []

    for row in rows:
        if len(row) < 14:  # Убедимся, что поле study_load есть
            continue
        sleep = row[0]
        study_load = row[13]

        if sleep is None:
            continue

        if study_load == 1:
            loaded_sleeps.append(float(sleep))
        else:
            normal_sleeps.append(float(sleep))

    # Если нет данных по нагрузке, график не строим
    if not normal_sleeps or not loaded_sleeps:
        return None

    avg_normal = sum(normal_sleeps) / len(normal_sleeps)
    avg_loaded = sum(loaded_sleeps) / len(loaded_sleeps)

    fig, ax = plt.subplots(figsize=(7, 4.5))

    labels = ["Обычные дни", "Дни с нагрузкой"]
    values = [avg_normal, avg_loaded]
    colors = ["#34D399", "#F87171"]

    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=3)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            f"{val:.1f} ч",
            ha="center", va="bottom",
            fontsize=12, fontweight="bold", color="#374151",
        )

    ax.set_title("Влияние учебной нагрузки на сон", fontsize=15, fontweight='bold', pad=15, color="#1F2937")
    ax.set_ylabel("Средний сон (часы)", fontsize=11)
    ax.set_ylim(0, max(values) + 1.5)
    ax.grid(True, axis="y", linestyle="-", alpha=0.1)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    return _save_to_tempfile(fig)
# ============================================================
# ГРАФИК 5. Сон в зависимости от времени учебы (для студентов)
# ============================================================

def make_study_time_chart(rows):
    """
    Строит график: средний сон в зависимости от времени учебы.
    rows — из get_checkins_for_analysis:
        row[0] — sleep_duration
        row[12] — shift_type (например, "Учёба: Утро", "Учёба: Вечер")
    """
    if not rows:
        return None

    # Собираем данные по каждому типу учебы
    groups = {}
    for row in rows:
        if len(row) < 13:
            continue
        sleep = row[0]
        shift_type = row[12]

        if sleep is None or not shift_type:
            continue

        # Оставляем только записи про учебу
        if not shift_type.startswith("Учёба:"):
            continue

        time_label = shift_type.replace("Учёба: ", "")
        if time_label not in groups:
            groups[time_label] = []
        groups[time_label].append(float(sleep))

    if len(groups) < 2:
        return None

    # Считаем средние
    labels = sorted(groups.keys(), key=lambda x: (
        ["Утро", "День", "Вечер", "Весь день", "Ночь"].index(x)
        if x in ["Утро", "День", "Вечер", "Весь день", "Ночь"] else 99
    ))
    values = [sum(groups[label]) / len(groups[label]) for label in labels]

    # Цвета: чем больше учебы, тем краснее
    colors_map = {
        "Утро": "#34D399",
        "День": "#60A5FA",
        "Вечер": "#FBBF24",
        "Весь день": "#F87171",
        "Ночь": "#A78BFA",
    }
    colors = [colors_map.get(l, "#9CA3AF") for l in labels]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=3)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            f"{val:.1f} ч",
            ha="center", va="bottom",
            fontsize=12, fontweight="bold", color="#374151",
        )

    avg = sum(values) / len(values)
    ax.axhline(avg, color="#9CA3AF", linestyle="--", linewidth=1.5,
               label=f"Среднее: {avg:.1f} ч", zorder=2)

    ax.set_title("Сон в зависимости от времени учебы",
                 fontsize=15, fontweight='bold', pad=15, color="#1F2937")
    ax.set_ylabel("Средний сон (часы)", fontsize=11)
    ax.set_ylim(0, max(values) + 1.5)
    ax.grid(True, axis="y", linestyle="-", alpha=0.1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(frameon=False)

    return _save_to_tempfile(fig)