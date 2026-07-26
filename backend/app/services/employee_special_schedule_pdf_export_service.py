from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_DIR = PROJECT_ROOT / "desktop"
if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_DIR))

from services.export_service import export_rows_to_pdf  # noqa: E402


STATUS_COLORS = {
    "ESCALADO": ("#DBEAFE", "#1D4ED8"),
    "COMPARECEU": ("#DCFCE7", "#166534"),
    "NAO COMPARECEU": ("#FEE2E2", "#B91C1C"),
}


def _fit_text(value, max_width, font_name="Helvetica", font_size=5.6):
    text = str(value or "-")
    if stringWidth(text, font_name, font_size) <= max_width:
        return text
    while len(text) > 3 and stringWidth(f"{text[:len(text) - 3]}...", font_name, font_size) > max_width:
        text = text[:-1]
    return f"{text.rstrip()}..."


def export_executive_special_schedule_pdf(
    rows: list[dict],
    output_path: str | Path,
    *,
    report_date: str,
    schedule_type: str,
    generated_by: str,
) -> Path:
    """Gera a escala em uma única página A4, no mesmo padrão executivo do absenteísmo."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    margin = 28
    content_width = page_width - (margin * 2)
    pdf = canvas.Canvas(str(path), pagesize=A4)

    def fill(hex_color):
        pdf.setFillColor(colors.HexColor(hex_color))

    def stroke(hex_color):
        pdf.setStrokeColor(colors.HexColor(hex_color))

    header_height = 66
    header_y = page_height - margin - header_height
    fill("#0B3D91")
    pdf.roundRect(margin, header_y, content_width, header_height, 8, fill=1, stroke=0)
    logo_path = DESKTOP_DIR / "assets" / "app-logo-cover.png"
    if logo_path.exists():
        try:
            pdf.drawImage(ImageReader(str(logo_path)), margin + 12, header_y + 12, width=42, height=42, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(margin + 66, header_y + 38, "RELATÓRIO EXECUTIVO DE ESCALA")
    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(margin + 66, header_y + 22, "Escala de domingo e feriado")

    y = header_y - 25
    metadata = [
        ("DATA DA ESCALA", report_date),
        ("TIPO", schedule_type),
        ("RESPONSÁVEL", generated_by),
        ("EMISSÃO", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    column_width = content_width / len(metadata)
    for index, (label, value) in enumerate(metadata):
        x = margin + (index * column_width)
        pdf.setFillColor(colors.HexColor("#64748B"))
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(x, y, label)
        pdf.setFillColor(colors.HexColor("#0F172A"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(x, y - 12, _fit_text(value, column_width - 8, font_size=8))

    statuses = [str(row.get("status") or "ESCALADO").upper() for row in rows]
    total = len(rows)
    confirmed = statuses.count("COMPARECEU")
    pending = statuses.count("ESCALADO")
    absent = statuses.count("NAO COMPARECEU")
    dsr_count = sum(1 for row in rows if row.get("dsr_date") and row.get("dsr_date") != "Não se aplica")
    cards = [("TOTAL", total), ("COMPARECEU", confirmed), ("PENDENTE", pending), ("NÃO COMPARECEU", absent), ("DSR PREVISTA", dsr_count)]
    cards_y = y - 55
    card_gap = 7
    card_width = (content_width - (card_gap * 4)) / 5
    for index, (label, value) in enumerate(cards):
        x = margin + index * (card_width + card_gap)
        fill("#FFFFFF")
        stroke("#CBD5E1")
        pdf.roundRect(x, cards_y, card_width, 40, 6, fill=1, stroke=1)
        pdf.setFillColor(colors.HexColor("#0B3D91"))
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawCentredString(x + card_width / 2, cards_y + 21, str(value))
        pdf.setFillColor(colors.HexColor("#475569"))
        pdf.setFont("Helvetica-Bold", 6.1)
        pdf.drawCentredString(x + card_width / 2, cards_y + 9, label)

    chart_top = cards_y - 17
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawString(margin, chart_top, "ESCALADOS POR ÁREA")
    area_counts = {}
    for row in rows:
        area = str(row.get("area") or "OUTROS").upper()
        area_counts[area] = area_counts.get(area, 0) + 1
    ordered_areas = [area for area in ("LBS", "RTG", "ADM", "PCM") if area in area_counts]
    ordered_areas.extend(sorted(area for area in area_counts if area not in ordered_areas))
    max_count = max(area_counts.values(), default=1)
    bar_y = chart_top - 14
    for area in ordered_areas[:5]:
        count = area_counts[area]
        pdf.setFillColor(colors.HexColor("#475569"))
        pdf.setFont("Helvetica-Bold", 6.8)
        pdf.drawString(margin, bar_y + 2, area)
        bar_x = margin + 34
        bar_width = 190 * (count / max_count)
        fill("#2563EB")
        pdf.roundRect(bar_x, bar_y, max(3, bar_width), 8, 3, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#0F172A"))
        pdf.setFont("Helvetica-Bold", 6.8)
        pdf.drawString(bar_x + max(3, bar_width) + 5, bar_y + 2, str(count))
        bar_y -= 11

    table_top = bar_y - 8
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawString(margin, table_top, "TABELA OPERACIONAL")
    table_y = table_top - 15
    columns = [("DATA", 72), ("DIA", 57), ("ÁREA", 32), ("MATRÍCULA", 48), ("COLABORADOR", 125), ("FUNÇÃO / TURNO", 111), ("SITUAÇÃO", 56), ("DSR", 38)]
    header_height = 16
    x = margin
    fill("#0B3D91")
    pdf.rect(margin, table_y - header_height + 3, content_width, header_height, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 6.1)
    for label, width in columns:
        pdf.drawString(x + 3, table_y - 7, label)
        x += width
    table_y -= header_height
    available = table_y - margin - 20
    row_height = min(9.5, max(6.4, available / max(1, len(rows))))
    for row in rows:
        if table_y - row_height < margin + 20:
            break
        status = str(row.get("status") or "ESCALADO").upper().replace("_", " ")
        bg, fg = STATUS_COLORS.get(status, ("#F8FAFC", "#334155"))
        fill(bg)
        pdf.rect(margin, table_y - row_height, content_width, row_height, fill=1, stroke=0)
        stroke("#E2E8F0")
        pdf.line(margin, table_y - row_height, margin + content_width, table_y - row_height)
        values = [row.get("schedule_date"), row.get("schedule_weekday"), row.get("area"), row.get("registration"), row.get("employee"), row.get("function_shift"), status, row.get("dsr_date")]
        x = margin
        for index, ((_, width), value) in enumerate(zip(columns, values)):
            pdf.setFillColor(colors.HexColor(fg if index == 6 else "#0F172A"))
            pdf.setFont("Helvetica-Bold" if index in (2, 4, 6) else "Helvetica", 5.2)
            pdf.drawString(x + 3, table_y - row_height + 2.1, _fit_text(value, width - 6, font_size=5.2))
            x += width
        table_y -= row_height

    footer_y = margin - 2
    stroke("#CBD5E1")
    pdf.line(margin, footer_y + 13, page_width - margin, footer_y + 13)
    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(margin, footer_y + 3, "Sistema de Gestão de Manutenção | Documento gerado automaticamente")
    pdf.drawRightString(page_width - margin, footer_y + 3, "Página 1/1")
    pdf.save()
    return path


def export_special_schedule_pdf(
    rows: list[dict],
    output_path: str | Path,
    *,
    subtitle: str,
    generated_by: str,
) -> Path:
    logo_path = DESKTOP_DIR / "assets" / "app-logo-cover.png"
    columns = [
        ("DATA DA ESCALA", "schedule_date"),
        ("DIA", "schedule_weekday"),
        ("TIPO", "schedule_type"),
        ("ÁREA", "area"),
        ("COLABORADOR", "employee"),
        ("MATRÍCULA", "registration"),
        ("FUNÇÃO / TURNO", "function_shift"),
        ("SITUAÇÃO", "status"),
        ("DSR PREVISTA", "dsr_date"),
    ]
    return export_rows_to_pdf(
        "HISTÓRICO DE ESCALA DE DOMINGO E FERIADO",
        subtitle,
        columns,
        rows,
        output_path,
        logo_path=logo_path if logo_path.exists() else None,
        generated_by=generated_by,
        period_label="Datas e dias da semana das escalas registradas",
    )
