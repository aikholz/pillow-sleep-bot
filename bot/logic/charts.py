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
    dates = []
    sleeps = []

    for row in rows:
        if len(row) >= 2 and row[0] is not None and row[1] is not None:
            dates.append(row[0])
            sleeps.append(float(row[1]))

    if not dates:
        return None

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(dates, sleeps, marker="o", color="#3B82F6", linewidth=2, markersize=6, zorder=3)
    ax.fill_between(dates, sleeps, alpha=0.1, color="#3B82F6")

    avg = sum(sleeps) / len(sleeps)
    ax.axhline(avg, color="#EF4444", linestyle="--", linewidth=1.5, label=f"Среднее: {avg:.1f} ч", zorder=2)

    ax.set_title("Сон по дням", fontsize=15, fontweight='bold', pad=15, color="#1F2937")
    ax.set_ylabel("Часы", fontsize=11)
    ax.grid(True, axis="y", linestyle="-", alpha=0.1)

    ax.xaxis.set_major_formatter(DateFormatter("%d.%m"))
    if len(dates) > 7:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 7)))

    fig.autofmt_xdate()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(frameon=False, loc='lower right')

    return _save_to_tempfile(fig)


# ============================================================
# ГРАФИК 2. Средний сон по типам смен (столбцы)
# ============================================================

def make_shift_chart(shift_stats):
    if not shift_stats:
        return None

    valid = {k: v for k, v in shift_stats.items() if v.get("avg_sleep") is not None}
    if len(valid) < 2:
        return None

    items = sorted(valid.items(), key=lambda x: x[1]["avg_sleep"])
    labels = [k for k, _ in items]
    values = [v["avg_sleep"] for _, v in items]
    colors = ["#F87171", "#FBBF24", "#34D399", "#60A5FA", "#A78BFA"][:len(items)]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=3)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{val:.1f} ч", ha="center", va="bottom", fontsize=12, fontweight="bold", color="#374151")

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
# ГРАФИК 3. Циркадный ритм
# ============================================================

def make_circadian_chart(circ):
    if not circ:
        return None

    fig, ax = plt.subplots(figsize=(8, 4.5))

    wd_sleep = circ["weekday_sleep"] % 24
    we_sleep = circ["weekend_sleep"] % 24
    wd_wake = circ["weekday_wake"] % 24
    we_wake = circ["weekend_wake"] % 24

    def _shift(h):
        return h + 24 if h < 12 else h

    ax.scatter([_shift(wd_sleep), _shift(we_sleep)], [1, 2], s=150, color=["#3B82F6", "#F87171"], zorder=4)
    ax.scatter([_shift(wd_wake), _shift(we_wake)], [1, 2], s=150, color=["#10B981", "#F59E0B"], marker="^", zorder=4)

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

    ax.set_xlim(20, 36)
    ticks = list(range(20, 24)) + list(range(24, 37))
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{h % 24:02d}:00" for h in ticks], rotation=45)

    ax.set_yticks([1, 2])
    ax.set_yticklabels(["Будни", "Выходные"], fontsize=12, fontweight="bold")
    ax.set_ylim(0.5, 2.5)

    ax.set_title(f"Циркадный ритм (сдвиг: {circ['social_jetlag_hours']:.1f} ч)",
                 fontsize=15, fontweight='bold', pad=20, color="#1F2937")

    ax.grid(True, axis="x", linestyle="--", alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#3B82F6', markersize=10, label='Сон (будни)'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#F87171', markersize=10, label='Сон (вых.)'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor='#10B981', markersize=10, label='Подъем (будни)'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor='#F59E0B', markersize=10, label='Подъем (вых.)')
    ]
    ax.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, -0.15),
              ncol=4, frameon=False, fontsize=10)

    plt.tight_layout()
    return _save_to_tempfile(fig)


# ============================================================
# ГРАФИК 4. Учебная нагрузка (для студентов)
# ============================================================

def make_study_load_chart(rows):
    if not rows:
        return None

    normal_sleeps = []
    loaded_sleeps = []

    for row in rows:
        if len(row) < 14:
            continue
        sleep = row[0]
        study_load = row[13]

        if sleep is None:
            continue

        if study_load == 1:
            loaded_sleeps.append(float(sleep))
        else:
            normal_sleeps.append(float(sleep))

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
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{val:.1f} ч", ha="center", va="bottom", fontsize=12, fontweight="bold", color="#374151")

    ax.set_title("Влияние учебной нагрузки на сон", fontsize=15, fontweight='bold', pad=15, color="#1F2937")
    ax.set_ylabel("Средний сон (часы)", fontsize=11)
    ax.set_ylim(0, max(values) + 1.5)
    ax.grid(True, axis="y", linestyle="-", alpha=0.1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    return _save_to_tempfile(fig)


# ============================================================
# ГРАФИК 5. Сон в зависимости от времени учебы
# ============================================================

def make_study_time_chart(rows):
    if not rows:
        return None

    groups = {}
    for row in rows:
        if len(row) < 13:
            continue
        sleep = row[0]
        shift_type = row[12]

        if sleep is None or not shift_type:
            continue

        if not shift_type.startswith("Учёба:"):
            continue

        time_label = shift_type.replace("Учёба: ", "")
        if time_label not in groups:
            groups[time_label] = []
        groups[time_label].append(float(sleep))

    if len(groups) < 2:
        return None

    labels = sorted(groups.keys(), key=lambda x: (
        ["Утро", "День", "Вечер", "Весь день", "Ночь"].index(x)
        if x in ["Утро", "День", "Вечер", "Весь день", "Ночь"] else 99
    ))
    values = [sum(groups[label]) / len(groups[label]) for label in labels]

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
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{val:.1f} ч", ha="center", va="bottom", fontsize=12, fontweight="bold", color="#374151")

    avg = sum(values) / len(values)
    ax.axhline(avg, color="#9CA3AF", linestyle="--", linewidth=1.5, label=f"Среднее: {avg:.1f} ч", zorder=2)

    ax.set_title("Сон в зависимости от времени учебы", fontsize=15, fontweight='bold', pad=15, color="#1F2937")
    ax.set_ylabel("Средний сон (часы)", fontsize=11)
    ax.set_ylim(0, max(values) + 1.5)
    ax.grid(True, axis="y", linestyle="-", alpha=0.1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(frameon=False)

    return _save_to_tempfile(fig)


# ============================================================
# ГРАФИК 6. Динамика прогресса (две оси)
# ============================================================

def make_progress_chart(rows):
    """График динамики прогресса (сон и качество)."""
    if len(rows) < 3:
        return None

    dates = [r[0] for r in rows]
    sleeps = [r[1] for r in rows]
    quality = [r[2] for r in rows]

    fig, ax1 = plt.subplots(figsize=(10, 5))

    # Ось сна
    color = '#3B82F6'
    ax1.set_xlabel('Дата')
    ax1.set_ylabel('Сон (часы)', color=color)
    ax1.plot(dates, sleeps, marker='o', color=color, linewidth=2, label='Сон')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.axhline(y=7.5, color='red', linestyle='--', alpha=0.5, label='Норма сна')

    # Вторая ось
    ax2 = ax1.twinx()
    color = '#F59E0B'
    ax2.set_ylabel('Качество (1-5)', color=color)
    ax2.plot(dates, quality, marker='s', color=color, linewidth=2, label='Качество')
    ax2.tick_params(axis='y', labelcolor=color)
    ax2.set_ylim(0, 5.5)

    ax1.xaxis.set_major_formatter(DateFormatter("%d.%m"))
    if len(dates) > 7:
        ax1.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 7)))
    fig.autofmt_xdate()
    ax1.grid(True, alpha=0.3)

    plt.title('Динамика твоего прогресса', fontsize=15, fontweight='bold')
    plt.tight_layout()
    return _save_to_tempfile(fig)