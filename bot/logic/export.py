import os
import csv
import tempfile
import time
from datetime import date, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from bot.logic.charts import (
    make_sleep_by_day_chart,
    make_circadian_chart,
    make_study_load_chart,
    make_study_time_chart,
)
from bot.logic.sleep_model import analyze_circadian
from bot.database.db import get_checkins_with_dates, get_checkins_for_analysis


def _wait_for_file(path, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return True
        time.sleep(0.1)
    return False


def generate_csv(telegram_id):
    rows = get_checkins_with_dates(telegram_id)
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8-sig",
                                      dir=tempfile.gettempdir(), newline="")
    writer = csv.writer(tmp, delimiter=";")
    writer.writerow(["Дата", "Сон (ч)", "Качество", "Настроение", "Энергия", "Стресс", "Кофеин", "Экран", "Активность", "Тип смены"])

    for row in rows:
        checkin_date = row[0]
        date_str = checkin_date.strftime("%d.%m.%Y") if isinstance(checkin_date, date) else str(checkin_date)
        writer.writerow([
            date_str,
            round(row[1], 1) if row[1] is not None else "",
            row[2] if row[2] is not None else "",
            row[3] if row[3] is not None else "",
            row[4] if row[4] is not None else "",
            row[5] if row[5] is not None else "",
            row[6] if row[6] is not None else "",
            row[7] if row[7] is not None else "",
            row[8] if row[8] is not None else "",
            row[9] if row[9] is not None else "",
        ])
    tmp.close()
    return tmp.name


def generate_pdf(rows, user_info, period_rows):
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=tempfile.gettempdir())
    tmp.close()

    # Регистрируем шрифт для кириллицы
    # Используем шрифт из библиотеки matplotlib (он всегда есть)
    import matplotlib.font_manager as fm
    font_path = fm.findfont("DejaVu Sans")
    pdfmetrics.registerFont(TTFont('Arial', font_path))
    doc = SimpleDocTemplate(tmp.name, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontName='Arial', fontSize=20, spaceAfter=20, textColor=colors.HexColor("#1F2937"))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Heading2'], fontName='Arial', fontSize=14, spaceAfter=10, textColor=colors.HexColor("#4B5563"))
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName='Arial')

    elements = []
    elements.append(Paragraph("Отчёт о сне", title_style))
    elements.append(Paragraph(f"Пользователь: {user_info['name']}", subtitle_style))
    elements.append(Paragraph(f"Возраст: {user_info['age']} лет", normal_style))
    elements.append(Paragraph(f"Категория: {user_info['category']}", normal_style))
    elements.append(Paragraph(f"Дата отчёта: {date.today().strftime('%d.%m.%Y')}", normal_style))
    elements.append(Spacer(1, 20))

    sleeps = [float(r[0]) for r in rows if r[0] is not None]
    avg_sleep = sum(sleeps) / len(sleeps) if sleeps else 0

    data = [["Показатель", "Значение"], ["Средний сон", f"{avg_sleep:.1f} ч"], ["Дней заполнено", f"{len(rows)}"]]
    table = Table(data, colWidths=[7 * cm, 7 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#F3F4F6")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # --- Графики ---
    elements.append(Paragraph("Графики", subtitle_style))
    elements.append(Spacer(1, 10))

    chart_paths = []

    # 1. Сон по дням
    chart1 = make_sleep_by_day_chart(period_rows)
    if chart1 and _wait_for_file(chart1):
        chart_paths.append(chart1)
        elements.append(Image(chart1, width=16 * cm, height=9 * cm))
        elements.append(Spacer(1, 10))

    # 2. Циркадный ритм
    circ = analyze_circadian(period_rows)
    if circ:
        chart2 = make_circadian_chart(circ)
        if chart2 and _wait_for_file(chart2):
            chart_paths.append(chart2)
            elements.append(Image(chart2, width=16 * cm, height=8 * cm))
            elements.append(Spacer(1, 10))

    # 3. Графики для студентов
    category = user_info.get("category", "")
    telegram_id = user_info.get("telegram_id")

    if "Учебный" in category and telegram_id:
        all_rows = get_checkins_for_analysis(telegram_id)
        # Учебная нагрузка
        chart3 = make_study_load_chart(all_rows)
        if chart3 and _wait_for_file(chart3):
            chart_paths.append(chart3)
            elements.append(Paragraph("Влияние учебной нагрузки на сон", normal_style))
            elements.append(Image(chart3, width=16 * cm, height=8 * cm))
            elements.append(Spacer(1, 10))

        # Время учебы
        chart4 = make_study_time_chart(all_rows)
        if chart4 and _wait_for_file(chart4):
            chart_paths.append(chart4)
            elements.append(Paragraph("Сон и время учебы", normal_style))
            elements.append(Image(chart4, width=16 * cm, height=8 * cm))
            elements.append(Spacer(1, 10))

    doc.build(elements)

    for p in chart_paths:
        if p and os.path.exists(p):
            try: os.remove(p)
            except: pass
    return tmp.name