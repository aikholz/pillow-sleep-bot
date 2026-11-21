def make_progress_chart(rows):
    """График динамики прогресса."""
    import matplotlib.pyplot as plt
    from matplotlib.dates import DateFormatter
    import matplotlib.dates as mdates
    import numpy as np

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