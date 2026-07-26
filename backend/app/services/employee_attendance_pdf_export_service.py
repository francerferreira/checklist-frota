from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

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


def export_employee_attendance_pdf(
    title: str,
    subtitle: str,
    columns: list[tuple[str, str]],
    rows: list[dict],
    output_path: str | Path,
    *,
    generated_by: str = "",
    period_label: str | None = None,
) -> Path:
    logo_path = DESKTOP_DIR / "assets" / "app-logo-cover.png"
    return export_rows_to_pdf(
        title,
        subtitle,
        columns,
        rows,
        output_path,
        logo_path=logo_path if logo_path.exists() else None,
        generated_by=generated_by,
        period_label=period_label,
    )


STATUS_COLORS = {
    "PRESENTE": ("#DCFCE7", "#166534"),
    "FALTA": ("#FEE2E2", "#B91C1C"),
    "ATESTADO": ("#FFEDD5", "#C2410C"),
    "FERIAS": ("#FEF3C7", "#A16207"),
    "DSR": ("#E0E7FF", "#3730A3"),
    "AFASTADO": ("#FEE2E2", "#B91C1C"),
}


def _fit_text(value, max_width, font_name="Helvetica", font_size=6.2):
    text = str(value or "-")
    if stringWidth(text, font_name, font_size) <= max_width:
        return text
    while len(text) > 3 and stringWidth(f"{text[:len(text) - 3]}...", font_name, font_size) > max_width:
        text = text[:-1]
    return f"{text.rstrip()}..."


def export_executive_employee_attendance_pdf(
    rows: list[dict],
    output_path: str | Path,
    *,
    report_date: str,
    shift_label: str,
    area_label: str,
    generated_by: str,
) -> Path:
    """Gera o relatório executivo de absenteísmo em uma única página A4 retrato."""
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

    # Cabeçalho executivo institucional.
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
    pdf.drawString(margin + 66, header_y + 38, "RELATÓRIO EXECUTIVO DE ABSENTEÍSMO")
    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(margin + 66, header_y + 22, "Sistema de Gestão de Manutenção Portuária")
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawRightString(page_width - margin - 12, header_y + 22, "PORTO CHIBATÃO")

    # Metadados do filtro utilizado.
    y = header_y - 25
    metadata = [
        ("DATA", report_date),
        ("TURNO", shift_label),
        ("ÁREA", area_label),
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

    # Indicadores executivos.
    statuses = [str(row.get("status") or "PRESENTE").upper() for row in rows]
    total = len(rows)
    present = statuses.count("PRESENTE")
    absent = sum(statuses.count(kind) for kind in ("FALTA", "AFASTADO", "DSR"))
    vacations = statuses.count("FERIAS")
    certificates = statuses.count("ATESTADO")
    frequency = round((present / total) * 100) if total else 0
    cards = [("TOTAL", total), ("PRESENTES", present), ("AUSENTES", absent), ("FÉRIAS", vacations), ("ATESTADOS", certificates), ("FREQUÊNCIA", f"{frequency}%")]
    cards_y = y - 55
    card_gap = 7
    card_width = (content_width - (card_gap * 5)) / 6
    for index, (label, value) in enumerate(cards):
        x = margin + index * (card_width + card_gap)
        fill("#FFFFFF")
        stroke("#CBD5E1")
        pdf.roundRect(x, cards_y, card_width, 40, 6, fill=1, stroke=1)
        pdf.setFillColor(colors.HexColor("#0B3D91"))
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawCentredString(x + card_width / 2, cards_y + 21, str(value))
        pdf.setFillColor(colors.HexColor("#475569"))
        pdf.setFont("Helvetica-Bold", 6.2)
        pdf.drawCentredString(x + card_width / 2, cards_y + 9, label)

    # Gráfico horizontal compacto por área.
    chart_top = cards_y - 17
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawString(margin, chart_top, "COLABORADORES POR ÁREA")
    area_counts = {}
    for row in rows:
        area = str(row.get("area") or "OUTROS").upper()
        area_counts[area] = area_counts.get(area, 0) + 1
    ordered_areas = [area for area in ("LBS", "RTG", "PCM", "ADM") if area in area_counts]
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

    # Tabela operacional compacta.
    table_top = bar_y - 8
    pdf.setFillColor(colors.HexColor("#0B3D91"))
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawString(margin, table_top, "TABELA OPERACIONAL")
    table_y = table_top - 15
    columns = [("ÁREA", 46), ("MATRÍCULA", 53), ("COLABORADOR", 166), ("FUNÇÃO", 137), ("TURNO", 70), ("STATUS", 67)]
    header_height = 16
    x = margin
    fill("#0B3D91")
    pdf.rect(margin, table_y - header_height + 3, content_width, header_height, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 6.3)
    for label, width in columns:
        pdf.drawString(x + 4, table_y - 7, label)
        x += width
    table_y -= header_height
    row_height = max(7.2, min(10, (table_y - margin - 24) / max(1, len(rows))))
    for row in rows:
        if table_y - row_height < margin + 20:
            break
        status = str(row.get("status") or "PRESENTE").upper()
        bg, fg = STATUS_COLORS.get(status, ("#F8FAFC", "#334155"))
        fill(bg)
        pdf.rect(margin, table_y - row_height, content_width, row_height, fill=1, stroke=0)
        stroke("#E2E8F0")
        pdf.line(margin, table_y - row_height, margin + content_width, table_y - row_height)
        values = [row.get("area"), row.get("matricula"), row.get("colaborador"), row.get("funcao"), row.get("turno"), status.replace("_", " ")]
        x = margin
        for index, ((_, width), value) in enumerate(zip(columns, values)):
            pdf.setFillColor(colors.HexColor(fg if index == 5 else "#0F172A"))
            pdf.setFont("Helvetica-Bold" if index in (0, 2, 5) else "Helvetica", 5.9)
            pdf.drawString(x + 4, table_y - row_height + 3, _fit_text(value, width - 8, font_size=5.9))
            x += width
        table_y -= row_height

    # Rodapé fixo de uma página.
    footer_y = margin - 2
    stroke("#CBD5E1")
    pdf.line(margin, footer_y + 13, page_width - margin, footer_y + 13)
    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(margin, footer_y + 3, "Sistema PCM | Porto Chibatão | Documento gerado automaticamente")
    pdf.drawRightString(page_width - margin, footer_y + 3, "Página 1/1")
    pdf.save()
    return path
