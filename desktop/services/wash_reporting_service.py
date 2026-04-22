from __future__ import annotations

import calendar as month_calendar
from datetime import date, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .export_service import (
    _build_cover_page,
    _build_signature_block,
    _build_summary_cards,
    _draw_page_frame,
    _key_value_table,
    _safe_paragraph_text,
    _styles,
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

    story = _build_cover_page(
        "Relatório mensal de lavagens",
        f"Checklist de Frota - {period_label}",
        generated_by,
        logo_path,
        styles,
        landscape_mode=True,
    )
    story.append(PageBreak())
    story.extend(
        _build_summary_cards(
            [
                ("Lavados no mês", str(resumo.get("lavados_mes", 0))),
                ("Valor total", _format_currency(total_value)),
                ("Categorias atendidas", str(len(indicadores.get("por_categoria", [])))),
                ("Veículos lavados", str(len(indicadores.get("por_veiculo", [])))),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Indicadores por categoria", styles["section"]))
    story.append(Spacer(1, 4))
    story.append(
        _key_value_table(
            [
                [
                    item.get("categoria") or "-",
                    f"{item.get('quantidade', 0)} lavagem(ns) • {_format_currency(item.get('valor'))}",
                ]
                for item in indicadores.get("por_categoria", [])
            ]
            or [["Sem dados", "Não houve lavagens registradas no período."]],
            styles,
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Indicadores por veículo", styles["section"]))
    story.append(Spacer(1, 4))
    story.append(
        _key_value_table(
            [
                [
                    item.get("referencia") or "-",
                    f"{item.get('quantidade', 0)} lavagem(ns) • {_format_currency(item.get('valor'))}",
                ]
                for item in indicadores.get("por_veiculo", [])[:12]
            ]
            or [["Sem dados", "Não houve lavagens registradas no período."]],
            styles,
        )
    )
    story.append(Spacer(1, 10))
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
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#0B1220"))
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawRightString(document.leftMargin + document.width, 8 * mm, f"Valor total do mês: {_format_currency(total_value)}")
        canvas.restoreState()

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

