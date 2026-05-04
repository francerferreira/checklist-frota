from __future__ import annotations

import calendar as month_calendar
from datetime import date, datetime
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .export_service import (
    _build_cover_page,
    _build_signature_block,
    _chart_card,
    _draw_page_frame,
    _safe_paragraph_text,
    _styles,
    _truncate_label,
    make_default_export_path,
)
from .message_service import MessagePackage


def build_wash_month_rows(overview: dict) -> list[dict]:
    rows: list[dict] = []
    for item in overview.get("historico", []):
        if item.get("status") != "LAVADO":
            continue
        vehicle = item.get("vehicle") or {}
        rows.append(
            {
                "data": _format_datetime(item.get("wash_date")),
                "referencia": item.get("referencia") or "-",
                "placa": vehicle.get("placa") or "-",
                "modelo": vehicle.get("modelo") or "-",
                "carreta": item.get("carreta") or "-",
                "tipo": item.get("tipo_equipamento") or "-",
                "turno": (item.get("turno") or "-").title(),
                "local": item.get("local") or "-",
                "valor": _format_currency(item.get("valor")),
            }
        )
    return rows


def export_wash_month_pdf(
    overview: dict,
    *,
    output_path: str | Path | None = None,
    logo_path: str | Path | None = None,
    generated_by: str = "",
) -> Path:
    path = Path(output_path or make_default_export_path("lavagens_mensal", "pdf"))
    path.parent.mkdir(parents=True, exist_ok=True)

    periodo = overview.get("periodo") or {}
    resumo = overview.get("resumo") or {}
    indicadores = overview.get("indicadores") or {}
    rows = build_wash_month_rows(overview)
    period_label = periodo.get("rotulo") or f"{periodo.get('mes', '-')}/{periodo.get('ano', '-')}"
    total_value = resumo.get("valor_total") or 0

    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=40 * mm,
        bottomMargin=14 * mm,
    )
    styles = _styles()
    wash_styles = _wash_styles(styles)

    story = _build_cover_page(
        "Relatório mensal de lavagens",
        f"Checklist de Frota - {period_label}",
        generated_by,
        logo_path,
        styles,
        landscape_mode=True,
    )
    story.append(PageBreak())
    story.append(Paragraph("Lavagens executadas", styles["section"]))
    story.append(Spacer(1, 4))

    headers = [
        "Data",
        "Referência",
        "Placa",
        "Modelo",
        "Carreta",
        "Categoria",
        "Turno",
        "Local",
        "Valor",
    ]
    table_data = [[Paragraph(title, styles["table_header"]) for title in headers]]
    for row in rows:
        table_data.append(
            [
                Paragraph(_safe_paragraph_text(row["data"]), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(row["referencia"]), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(row["placa"]), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(row["modelo"]), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(row["carreta"]), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(row["tipo"]), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(row["turno"]), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(row["local"]), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(row["valor"]), styles["table_cell"]),
            ]
        )

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Indicador por tipo de equipamento", styles["section"]))
    story.append(Spacer(1, 4))
    story.append(_build_wash_volume_chart(indicadores.get("por_categoria", []), indicadores.get("por_veiculo", []), wash_styles))
    story.append(Spacer(1, 10))
    story.append(_build_total_value_footer(total_value, wash_styles))
    story.append(Spacer(1, 12))
    story.extend(_build_signature_block(generated_by, styles))

    def footer(canvas, document):
        _draw_page_frame(
            canvas,
            document,
            generated_by,
            "Relatório mensal de lavagens",
            f"Programação e execução de {period_label}",
            logo_path,
        )

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path


def export_wash_schedule_pdf(
    overview: dict,
    *,
    output_path: str | Path | None = None,
    logo_path: str | Path | None = None,
    generated_by: str = "",
) -> Path:
    path = Path(output_path or make_default_export_path("lavagens_cronograma", "pdf"))
    path.parent.mkdir(parents=True, exist_ok=True)

    periodo = overview.get("periodo") or {}
    cronograma = (overview.get("cronograma") or {}).get("days", [])
    period_label = periodo.get("rotulo") or f"{periodo.get('mes', '-')}/{periodo.get('ano', '-')}"

    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=40 * mm,
        bottomMargin=14 * mm,
    )
    styles = _styles()

    story = _build_cover_page(
        "Cronograma mensal de lavagens",
        f"Checklist de Frota - {period_label}",
        generated_by,
        logo_path,
        styles,
        landscape_mode=True,
    )
    story.append(PageBreak())

    story.append(Paragraph("Cronograma mensal vivo", styles["section"]))
    story.append(Spacer(1, 4))

    year = int(periodo.get("ano") or date.today().year)
    month = int(periodo.get("mes") or date.today().month)
    today_iso = date.today().isoformat()
    day_map = {item.get("date"): item for item in cronograma}

    weeks = month_calendar.monthcalendar(year, month)
    while len(weeks) < 6:
        weeks.append([0] * 7)

    weekday_headers = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]
    table_data = [[Paragraph(f"<b>{header}</b>", styles["table_cell"]) for header in weekday_headers]]
    cell_backgrounds: list[tuple[tuple[int, int], str]] = []

    for row_index, week in enumerate(weeks[:6], start=1):
        row_cells = []
        for col_index, day_number in enumerate(week):
            if day_number == 0:
                row_cells.append(Paragraph("", styles["table_cell"]))
                cell_backgrounds.append(((col_index, row_index), "#F8FAFC"))
                continue

            day_iso = date(year, month, day_number).isoformat()
            payload = day_map.get(day_iso, {})
            morning_refs = ", ".join(item.get("referencia") or "-" for item in (payload.get("morning") or [])[:2])
            afternoon_refs = ", ".join(item.get("referencia") or "-" for item in (payload.get("afternoon") or [])[:2])
            morning_text = "sem lavagem" if payload.get("blocked_morning") else (morning_refs or "-")
            afternoon_text = "sem lavagem" if payload.get("blocked_afternoon") else (afternoon_refs or "-")
            items = (payload.get("morning") or []) + (payload.get("afternoon") or [])
            ok_count = sum(1 for item in items if item.get("status_execucao") == "LAVADO")
            no_count = sum(1 for item in items if item.get("status_execucao") == "NAO_CUMPRIDO")
            pending_count = sum(1 for item in items if item.get("status_execucao") == "PENDENTE")
            label = f"HOJE • {day_number}" if day_iso == today_iso else str(day_number)
            cell_html = (
                f"<b>{_safe_paragraph_text(label)}</b><br/>"
                f"<b>MANHÃ:</b> {_safe_paragraph_text(morning_text)}<br/>"
                f"<b>TARDE:</b> {_safe_paragraph_text(afternoon_text)}<br/>"
                f"<font color='#065F46'><b>OK {ok_count}</b></font>  "
                f"<font color='#991B1B'><b>X {no_count}</b></font>  "
                f"<font color='#6B7280'><b>PEND {pending_count}</b></font>"
            )
            row_cells.append(Paragraph(cell_html, styles["table_cell"]))
            cell_backgrounds.append(((col_index, row_index), "#DBEAFE" if day_iso == today_iso else "#EAF4FF"))
        table_data.append(row_cells)

    calendar_table = Table(
        table_data,
        colWidths=[doc.width / 7.0] * 7,
        rowHeights=[11 * mm] + [25 * mm] * 6,
        repeatRows=1,
    )
    table_style_rules = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
        ("LINEAFTER", (0, 0), (-2, -1), 0.25, colors.HexColor("#E2E8F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for (col, row), hex_color in cell_backgrounds:
        table_style_rules.append(("BACKGROUND", (col, row), (col, row), colors.HexColor(hex_color)))
    calendar_table.setStyle(TableStyle(table_style_rules))

    story.append(calendar_table)
    story.append(Spacer(1, 12))
    story.extend(_build_signature_block(generated_by, styles))

    def footer(canvas, document):
        _draw_page_frame(
            canvas,
            document,
            generated_by,
            "Cronograma mensal de lavagens",
            f"Programação operacional de {period_label}",
            logo_path,
        )

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path


def build_wash_tomorrow_message_package(payload: dict, generated_by: str = "") -> MessagePackage:
    date_label = _format_short_date(payload.get("date"))
    morning = payload.get("morning") or []
    afternoon = payload.get("afternoon") or []

    summary_items = [
        ("Data", date_label),
        ("Manhã", str(len(morning))),
        ("Tarde", str(len(afternoon))),
        ("Total", str(len(morning) + len(afternoon))),
    ]

    whatsapp_lines = [
        "*PROGRAMAÇÃO DE LAVAGEM - AMANHÃ*",
        f"_Data: {date_label}_",
    ]
    if generated_by:
        whatsapp_lines.append(f"_Emitido por: {generated_by}_")
    whatsapp_lines.extend(
        [
            "",
            "*Manhã*",
            *_slot_lines(morning),
            "",
            "*Tarde*",
            *_slot_lines(afternoon),
        ]
    )

    email_lines = [
        "PROGRAMAÇÃO DE LAVAGEM - AMANHÃ",
        f"Data: {date_label}",
    ]
    if generated_by:
        email_lines.append(f"Emitido por: {generated_by}")
    email_lines.extend(
        [
            "",
            "Manhã:",
            *_slot_lines(morning),
            "",
            "Tarde:",
            *_slot_lines(afternoon),
        ]
    )

    return MessagePackage(
        title="Mensagem operacional de lavagem",
        email_subject=f"Programação de lavagem - {date_label}",
        whatsapp_text="\n".join(whatsapp_lines).strip(),
        email_body="\n".join(email_lines).strip(),
        summary_items=summary_items,
    )


def _slot_lines(items: list[dict]) -> list[str]:
    if not items:
        return ["- Sem lavagem planejada."]
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        label = item.get("referencia") or "-"
        tipo = item.get("categoria_lavagem") or "-"
        lines.append(f"{index}. {label} - {tipo}")
    return lines


def _format_short_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y")
    except ValueError:
        return value


def _format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "")).strftime("%d/%m/%Y")
    except ValueError:
        return value


def _format_currency(value) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _wash_styles(styles):
    return {
        "spotlight_value": ParagraphStyle(
            "WashSpotlightValue",
            parent=styles["cover_title"],
            fontSize=26,
            leading=30,
            textColor=colors.white,
        ),
        "spotlight_label": ParagraphStyle(
            "WashSpotlightLabel",
            parent=styles["cover_band"],
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#DBEAFE"),
        ),
        "spotlight_caption": ParagraphStyle(
            "WashSpotlightCaption",
            parent=styles["body"],
            fontSize=10,
            leading=13,
            textColor=colors.white,
        ),
        "total_footer_label": ParagraphStyle(
            "WashTotalFooterLabel",
            parent=styles["summary_label"],
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#1E3A8A"),
        ),
        "total_footer_value": ParagraphStyle(
            "WashTotalFooterValue",
            parent=styles["cover_title"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0B1220"),
        ),
        "highlight_title": ParagraphStyle(
            "WashHighlightTitle",
            parent=styles["summary_label"],
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor("#475569"),
        ),
        "highlight_value": ParagraphStyle(
            "WashHighlightValue",
            parent=styles["body"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#0B1220"),
        ),
        "highlight_detail": ParagraphStyle(
            "WashHighlightDetail",
            parent=styles["table_cell"],
            fontSize=8.8,
            leading=11,
            textColor=colors.HexColor("#334155"),
        ),
    }


def _build_total_value_spotlight(total_value, lavados_mes: int, period_label: str, styles) -> Table:
    block = Table(
        [[
            Paragraph(
                f"FATURAMENTO DE LAVAGENS<br/>{_format_currency(total_value)}",
                styles["spotlight_value"],
            ),
            Paragraph(
                (
                    f"<b>Período:</b> {_safe_paragraph_text(period_label)}<br/>"
                    f"<b>Lavagens concluídas:</b> {_safe_paragraph_text(str(lavados_mes))}<br/>"
                    "Indicador financeiro principal do relatório mensal."
                ),
                styles["spotlight_caption"],
            ),
        ]],
        colWidths=[120 * mm, 126 * mm],
    )
    block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1D4ED8")),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#1E40AF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return block


def _wash_highlight_card(label: str, title: str, detail: str, styles) -> Table:
    card = Table(
            [[
                Paragraph(_safe_paragraph_text(label.upper()), styles["highlight_title"]),
                Paragraph(_safe_paragraph_text(title), styles["highlight_value"]),
                Paragraph(_safe_paragraph_text(detail), styles["highlight_detail"]),
            ]],
        colWidths=[118 * mm],
    )
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D9E2EF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return card


def _build_wash_volume_chart(category_rows: list[dict], vehicle_rows: list[dict], styles) -> Table:
    ordered = sorted(
        [
            {
                "label": item.get("categoria") or "-",
                "quantidade": int(item.get("quantidade", 0) or 0),
                "valor": float(item.get("valor", 0) or 0),
            }
            for item in category_rows
        ],
        key=lambda row: (row["quantidade"], row["valor"]),
        reverse=True,
    )
    if not ordered:
        return _wash_highlight_card("Sem dados", "Nenhuma lavagem registrada", "Não há dados para montar o gráfico.", styles)

    labels = [_truncate_label(row["label"], 18) for row in ordered]
    quantities = [row["quantidade"] for row in ordered]
    axis_max = max(1, max(quantities))

    drawing = Drawing(470, 185)
    drawing.add(String(10, 165, "Quantidade de lavagens por tipo", fontName="Helvetica-Bold", fontSize=11, fillColor=colors.HexColor("#0B1220")))

    chart = VerticalBarChart()
    chart.x = 18
    chart.y = 30
    chart.height = 118
    chart.width = 420
    chart.data = [tuple(quantities)]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.angle = 18
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 7.2
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = axis_max + max(1, round(axis_max * 0.2))
    chart.valueAxis.valueStep = max(1, int(round(chart.valueAxis.valueMax / 5)))
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.bars[0].fillColor = colors.HexColor("#2563EB")
    chart.bars[0].strokeColor = colors.HexColor("#1D4ED8")
    chart.bars[0].strokeWidth = 0.3
    drawing.add(chart)

    vehicle_names = [item.get("referencia") or "-" for item in vehicle_rows]
    unique_vehicles = []
    for name in vehicle_names:
        if name not in unique_vehicles:
            unique_vehicles.append(name)
    side_summary = _wash_highlight_card(
        "Resumo lateral",
        f"{len(unique_vehicles)} carro(s) lavado(s)",
        f"{', '.join(unique_vehicles[:8]) or 'Sem veículos'}",
        styles,
    )
    total_summary = _wash_highlight_card(
        "Total no gráfico",
        f"{sum(quantities)} lavagem(ns)",
        "Ordem do maior volume para o menor.",
        styles,
    )

    wrapper = Table(
        [[_chart_card(drawing, 163 * mm), Table([[side_summary], [Spacer(1, 4)], [total_summary]], colWidths=[74 * mm])]],
        colWidths=[168 * mm, 76 * mm],
    )
    wrapper.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return wrapper


def _build_total_value_footer(total_value, styles) -> Table:
    block = Table(
        [[
            Paragraph("VALOR TOTAL DAS LAVAGENS", styles["total_footer_label"]),
            Paragraph(_format_currency(total_value), styles["total_footer_value"]),
        ]],
        colWidths=[82 * mm, 162 * mm],
    )
    block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EAF4FF")),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#BFDBFE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return block

