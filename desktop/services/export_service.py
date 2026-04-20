from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from runtime_paths import exports_path


BRAND_BLUE = "#0B1220"
PRIMARY_BLUE = "#2563EB"
LIGHT_BG = "#F8FAFC"
MUTED = "#64748B"
SEVERITY_RED = "#B91C1C"
SEVERITY_RED_BG = "#FEE2E2"
SEVERITY_YELLOW = "#B45309"
SEVERITY_YELLOW_BG = "#FEF3C7"
SEVERITY_GREEN = "#166534"
SEVERITY_GREEN_BG = "#DCFCE7"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _default_export_path(prefix: str, suffix: str) -> Path:
    export_dir = exports_path()
    return export_dir / f"{prefix}_{_timestamp()}.{suffix}"


def make_default_export_path(prefix: str, suffix: str) -> str:
    return str(_default_export_path(prefix, suffix))


def export_rows_to_csv(
    columns: list[tuple[str, str]],
    rows: list[dict],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow([label for label, _ in columns])
        for row in rows:
            writer.writerow([_stringify(row.get(key)) for _, key in columns])
    return path


def export_rows_to_xlsx(
    title: str,
    columns: list[tuple[str, str]],
    rows: list[dict],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Relatório"

    sheet["A1"] = title
    sheet["A1"].font = Font(bold=True, size=15, color="FFFFFF")
    sheet["A1"].fill = PatternFill("solid", fgColor="0B1220")
    sheet["A1"].alignment = Alignment(horizontal="left", vertical="center")
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))

    for column_index, (label, _) in enumerate(columns, start=1):
        cell = sheet.cell(row=3, column=column_index, value=label)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2563EB")
        cell.alignment = Alignment(horizontal="left", vertical="center")

    for row_index, row in enumerate(rows, start=4):
        for column_index, (_, key) in enumerate(columns, start=1):
            cell = sheet.cell(row=row_index, column=column_index, value=_stringify(row.get(key)))
            cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    for column_index, (label, key) in enumerate(columns, start=1):
        values = [_stringify(row.get(key)) for row in rows]
        max_size = max([len(label)] + [len(value) for value in values] + [12])
        sheet.column_dimensions[get_column_letter(column_index)].width = min(max_size + 2, 36)

    workbook.save(path)
    return path


def export_rows_to_pdf(
    title: str,
    subtitle: str,
    columns: list[tuple[str, str]],
    rows: list[dict],
    output_path: str | Path,
    *,
    logo_path: str | Path | None = None,
    generated_by: str = "",
    period_label: str | None = None,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
    )

    styles = _styles()
    story = _build_cover_page(title, subtitle, generated_by, logo_path, styles, landscape_mode=True)
    story.append(PageBreak())
    story.extend(_build_header(title, subtitle, generated_by, logo_path, styles))
    story.extend(
        _build_summary_cards(
            [
                ("Total de linhas", str(len(rows))),
                ("Colunas", str(len(columns))),
                ("Período", period_label or f"Base consolidada até {datetime.now().strftime('%d/%m/%Y')}"),
                ("Semáforo executivo", _overall_priority_label(columns, rows)),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 6))
    story.append(Paragraph("Visão analítica consolidada", styles["section"]))
    story.append(Spacer(1, 4))

    chart_section = _build_chart_section(columns, rows, styles)
    if chart_section:
        story.extend(chart_section)
        story.append(Spacer(1, 8))

    ranking_section = _build_top_five_section(columns, rows, styles)
    if ranking_section:
        story.extend(ranking_section)
        story.append(Spacer(1, 8))

    table_data = [[Paragraph(label, styles["table_header"]) for label, _ in columns]]
    for row in rows:
        table_data.append(
            [Paragraph(_safe_paragraph_text(_stringify(row.get(key))), styles["table_cell"]) for _, key in columns]
        )

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY_BLUE)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT_BG)]),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    story.append(table)
    story.append(Spacer(1, 10))
    story.extend(_build_executive_conclusion(columns, rows, styles, period_label))
    story.append(Spacer(1, 10))
    story.extend(_build_signature_block(generated_by, styles))
    doc.build(
        story,
        onFirstPage=lambda canvas, document: _draw_footer(canvas, document, generated_by),
        onLaterPages=lambda canvas, document: _draw_footer(canvas, document, generated_by),
    )
    return path


def export_non_conformity_pdf(
    item: dict,
    *,
    output_path: str | Path,
    logo_path: str | Path | None = None,
    generated_by: str = "",
    before_image: bytes | None = None,
    after_image: bytes | None = None,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
    )
    styles = _styles()
    story = _build_cover_page(
        "Relatório de Não Conformidade",
        f"{item['veiculo']['frota']} - {item['item_nome']}",
        generated_by,
        logo_path,
        styles,
        landscape_mode=False,
    )
    story.append(PageBreak())
    story.extend(
        _build_header(
            "Relatório de Não Conformidade",
            f"{item['veiculo']['frota']} - {item['item_nome']}",
            generated_by,
            logo_path,
            styles,
        )
    )

    status_text = "Resolvida" if item.get("resolvido") else "Aberta"
    story.extend(
        _build_summary_cards(
            [
                ("Status", status_text),
                ("Veículo", item["veiculo"].get("frota") or "-"),
                ("Motorista", item["usuario"].get("nome") or "-"),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Resumo executivo da ocorrência", styles["section"]))
    story.append(Spacer(1, 4))
    info_rows = [
        ["Veículo", item["veiculo"].get("frota") or "-"],
        ["Tipo", item["veiculo"].get("tipo", "-").title()],
        ["Placa", item["veiculo"].get("placa") or "-"],
        ["Modelo", item["veiculo"].get("modelo") or "-"],
        ["Item", item.get("item_nome") or "-"],
        ["Status", status_text],
        ["Motorista", item["usuario"].get("nome") or "-"],
        ["Data de abertura", _format_datetime(item.get("created_at"))],
        ["Data de resolução", _format_datetime(item.get("data_resolucao"))],
        ["Código da peça", item.get("codigo_peca") or "-"],
        ["Descrição da peça", item.get("descricao_peca") or "-"],
        ["Observação", item.get("observacao") or "-"],
    ]
    story.append(_key_value_table(info_rows, styles))
    story.append(Spacer(1, 8))

    image_block = []
    if before_image:
        image_block.append(_reportlab_image(before_image, 86 * mm, 76 * mm))
    else:
        image_block.append(Paragraph("Sem foto antes", styles["muted_box"]))
    if after_image:
        image_block.append(_reportlab_image(after_image, 86 * mm, 76 * mm))
    else:
        image_block.append(Paragraph("Sem foto depois", styles["muted_box"]))

    image_table = Table(
        [
            [
                Paragraph("Foto antes", styles["section"]),
                Paragraph("Foto depois", styles["section"]),
            ],
            image_block,
        ],
        colWidths=[89 * mm, 89 * mm],
    )
    image_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("LINEBELOW", (0, 0), (-1, 0), 0.35, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(image_table)
    story.append(Spacer(1, 12))
    story.extend(_build_signature_block(generated_by, styles))
    doc.build(
        story,
        onFirstPage=lambda canvas, document: _draw_footer(canvas, document, generated_by),
        onLaterPages=lambda canvas, document: _draw_footer(canvas, document, generated_by),
    )
    return path


def export_vehicle_detail_pdf(
    vehicle: dict,
    occurrences: list[dict],
    *,
    output_path: str | Path,
    logo_path: str | Path | None = None,
    generated_by: str = "",
    vehicle_image: bytes | None = None,
    operational_history: list[dict] | None = None,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
    )
    styles = _styles()
    story = _build_cover_page(
        "Ficha de Equipamento",
        f"{vehicle.get('frota', '-')} - {vehicle.get('modelo', '-')}",
        generated_by,
        logo_path,
        styles,
        landscape_mode=False,
    )
    story.append(PageBreak())
    story.extend(
        _build_header(
            "Ficha de Equipamento",
            f"{vehicle.get('frota', '-')} - {vehicle.get('modelo', '-')}",
            generated_by,
            logo_path,
            styles,
        )
    )
    story.extend(
        _build_summary_cards(
            [
                ("Frota", vehicle.get("frota") or "-"),
                ("Tipo", (vehicle.get("tipo") or "-").title()),
                ("Não conformidades acumuladas", str(len(occurrences))),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Resumo técnico do ativo", styles["section"]))
    story.append(Spacer(1, 4))

    rows = [
        ["Frota", vehicle.get("frota") or "-"],
        ["Tipo", (vehicle.get("tipo") or "-").title()],
        ["Placa", vehicle.get("placa") or "-"],
        ["Modelo", vehicle.get("modelo") or "-"],
        ["Ano", vehicle.get("ano") or "-"],
        ["Chassi", vehicle.get("chassi") or "-"],
        ["Configuração", vehicle.get("configuracao") or "-"],
        ["Atividade", vehicle.get("atividade") or "-"],
        ["Status", vehicle.get("status") or "-"],
        ["Local", vehicle.get("local") or "-"],
        ["Descrição", vehicle.get("descricao") or "-"],
        ["Total de ocorrências de não conformidade", str(len(occurrences))],
    ]
    story.append(_key_value_table(rows, styles))
    story.append(Spacer(1, 8))

    if vehicle_image:
        story.append(Paragraph("Foto do equipamento", styles["section"]))
        story.append(Spacer(1, 4))
        story.append(_reportlab_image(vehicle_image, 170 * mm, 95 * mm))
        story.append(Spacer(1, 10))

    occ_columns = [
        ("Data", "created_at"),
        ("Item", "item_nome"),
        ("Status", "status_text"),
        ("Peça", "codigo_peca"),
        ("Motorista", "motorista"),
    ]
    occ_rows = []
    for item in occurrences:
        occ_rows.append(
            {
                "created_at": _format_datetime(item.get("created_at")),
                "item_nome": item.get("item_nome") or "-",
                "status_text": "Resolvida" if item.get("resolvido") else "Aberta",
                "codigo_peca": item.get("codigo_peca") or "-",
                "motorista": item.get("usuario", {}).get("nome") or "-",
            }
        )

    story.append(Spacer(1, 4))
    story.append(Paragraph("Ocorrências registradas", styles["section"]))
    story.append(Spacer(1, 4))

    if occ_rows:
        occ_table = Table(
            [[Paragraph(label, styles["table_header"]) for label, _ in occ_columns]]
            + [
                [Paragraph(_safe_paragraph_text(_stringify(row.get(key))), styles["table_cell"]) for _, key in occ_columns]
                for row in occ_rows
            ],
            repeatRows=1,
        )
        occ_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY_BLUE)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT_BG)]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(occ_table)
    else:
        story.append(Paragraph("Nenhuma não conformidade registrada para este equipamento.", styles["muted_box"]))

    if operational_history:
        history_columns = [
            ("Data", "date"),
            ("Origem", "origin"),
            ("Item", "item"),
            ("Status", "status"),
            ("Responsável", "owner"),
        ]
        history_rows = [
            {
                "date": _format_datetime(item.get("date")),
                "origin": item.get("origin") or "-",
                "item": item.get("item") or "-",
                "status": item.get("status") or "-",
                "owner": item.get("owner") or "-",
            }
            for item in operational_history[:80]
        ]
        story.append(Spacer(1, 10))
        story.append(Paragraph("Histórico operacional", styles["section"]))
        story.append(Spacer(1, 4))
        history_table = Table(
            [[Paragraph(label, styles["table_header"]) for label, _ in history_columns]]
            + [
                [Paragraph(_safe_paragraph_text(_stringify(row.get(key))), styles["table_cell"]) for _, key in history_columns]
                for row in history_rows
            ],
            repeatRows=1,
        )
        history_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY_BLUE)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT_BG)]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(history_table)

    story.append(Spacer(1, 12))
    story.extend(_build_signature_block(generated_by, styles))
    doc.build(
        story,
        onFirstPage=lambda canvas, document: _draw_footer(canvas, document, generated_by),
        onLaterPages=lambda canvas, document: _draw_footer(canvas, document, generated_by),
    )
    return path


def export_activity_pdf(
    activity: dict,
    *,
    output_path: str | Path,
    logo_path: str | Path | None = None,
    generated_by: str = "",
    item_images: dict[int, dict[str, bytes | None]] | None = None,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
    )
    styles = _styles()
    resumo = activity.get("resumo", {})
    itens = activity.get("itens", [])
    item_images = item_images or {}

    title = activity.get("titulo") or "Atividade em massa"
    subtitle = f"{activity.get('item_nome') or '-'} • {(activity.get('tipo_equipamento') or '-').title()}"

    story = _build_cover_page(title, subtitle, generated_by, logo_path, styles, landscape_mode=False)
    story.append(PageBreak())
    story.extend(_build_header(title, subtitle, generated_by, logo_path, styles))
    story.extend(
        _build_summary_cards(
            [
                ("Equipamentos", str(resumo.get("total", len(itens)))),
                ("Instalados", str(resumo.get("instalados", 0))),
                ("Não instalados", str(resumo.get("nao_instalados", 0))),
                ("Pendentes", str(resumo.get("pendentes", 0))),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Resumo da atividade", styles["section"]))
    story.append(Spacer(1, 4))
    story.append(
        _key_value_table(
            [
                ["Titulo", activity.get("titulo") or "-"],
                ["Modulo / componente", activity.get("item_nome") or "-"],
                ["Tipo de equipamento", (activity.get("tipo_equipamento") or "-").title()],
                ["Status", "Finalizada" if activity.get("status") == "FINALIZADA" else "Aberta"],
                ["Código da peça", activity.get("codigo_peca") or "-"],
                ["Descrição da peça", activity.get("descricao_peca") or "-"],
                ["Fornecedor", activity.get("fornecedor_peca") or "-"],
                ["Lote", activity.get("lote_peca") or "-"],
                ["Data de abertura", _format_datetime(activity.get("created_at"))],
                ["Data de fechamento", _format_datetime(activity.get("finalized_at"))],
                ["Observação geral", activity.get("observacao") or "-"],
            ],
            styles,
        )
    )
    story.append(Spacer(1, 8))

    summary_columns = [
        ("Frota", "frota"),
        ("Placa", "placa"),
        ("Modelo", "modelo"),
        ("Status da atividade", "status"),
        ("Instalado em", "instalado_em"),
        ("Executado por", "executado_por"),
    ]
    summary_rows = []
    for item in itens:
        veiculo = item.get("veiculo", {})
        summary_rows.append(
            {
                "frota": veiculo.get("frota") or "-",
                "placa": veiculo.get("placa") or "-",
                "modelo": veiculo.get("modelo") or "-",
                "status": _activity_item_status_text(item.get("status_execucao")),
                "instalado_em": _format_datetime(item.get("instalado_em")),
                "executado_por": item.get("executado_por_nome") or "-",
            }
        )

    story.append(Paragraph("Consolidado por equipamento", styles["section"]))
    story.append(Spacer(1, 4))
    summary_table = Table(
        [[Paragraph(label, styles["table_header"]) for label, _ in summary_columns]]
        + [
            [Paragraph(_safe_paragraph_text(_stringify(row.get(key))), styles["table_cell"]) for _, key in summary_columns]
            for row in summary_rows
        ],
        repeatRows=1,
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY_BLUE)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT_BG)]),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(summary_table)

    if itens:
        story.append(PageBreak())
        story.append(Paragraph("Caderno de evidências por equipamento", styles["section"]))
        story.append(Spacer(1, 6))

    for index, item in enumerate(itens):
        veiculo = item.get("veiculo", {})
        images = item_images.get(item.get("id"), {})
        before_image = images.get("before")
        after_image = images.get("after")
        status_text = _activity_item_status_text(item.get("status_execucao"))
        stamp = _activity_status_stamp(status_text, styles)

        item_header = Table(
            [[
                Paragraph(f"{veiculo.get('frota') or '-'} • {veiculo.get('modelo') or '-'}", styles["section"]),
                stamp,
            ]],
            colWidths=[132 * mm, 48 * mm],
        )
        item_header.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                    ("LINELEFT", (0, 0), (-1, -1), 1.0, colors.HexColor("#BFDBFE")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(item_header)
        story.append(Spacer(1, 6))
        story.append(
            _key_value_table(
                [
                    ["Frota", veiculo.get("frota") or "-"],
                    ["Placa", veiculo.get("placa") or "-"],
                    ["Modelo", veiculo.get("modelo") or "-"],
                    ["Status da atividade", status_text],
                    ["Executado em", _format_datetime(item.get("instalado_em"))],
                    ["Executado por", item.get("executado_por_nome") or "-"],
                    ["Login do executor", item.get("executado_por_login") or "-"],
                    ["Observação", item.get("observacao") or "-"],
                ],
                styles,
            )
        )
        story.append(Spacer(1, 6))

        image_block = []
        image_block.append(_reportlab_image(before_image, 86 * mm, 76 * mm) if before_image else Paragraph("Sem foto antes", styles["muted_box"]))
        image_block.append(_reportlab_image(after_image, 86 * mm, 76 * mm) if after_image else Paragraph("Sem foto depois", styles["muted_box"]))
        image_table = Table(
            [
                [Paragraph("Foto antes", styles["section"]), Paragraph("Foto depois", styles["section"])],
                image_block,
            ],
            colWidths=[89 * mm, 89 * mm],
        )
        image_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.35, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(image_table)
        if index < len(itens) - 1:
            story.append(Spacer(1, 10))
            story.append(PageBreak())

    story.append(Spacer(1, 12))
    story.extend(_build_signature_block(generated_by, styles))
    doc.build(
        story,
        onFirstPage=lambda canvas, document: _draw_footer(canvas, document, generated_by),
        onLaterPages=lambda canvas, document: _draw_footer(canvas, document, generated_by),
    )
    return path


def export_material_report_xlsx(
    report: dict,
    *,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()

    summary_sheet = workbook.active
    summary_sheet.title = "Resumo"
    summary_sheet["A1"] = "Relatório de Estoque"
    summary_sheet["A1"].font = Font(bold=True, size=15, color="FFFFFF")
    summary_sheet["A1"].fill = PatternFill("solid", fgColor="0B1220")
    summary_sheet.merge_cells("A1:B1")

    resumo = report.get("resumo", {})
    periodo = report.get("periodo", {})
    summary_rows = [
        ("Data inicial", periodo.get("data_inicial") or "-"),
        ("Data final", periodo.get("data_final") or "-"),
        ("Total de materiais", resumo.get("total_materiais", 0)),
        ("Abaixo do mínimo", resumo.get("abaixo_minimo", 0)),
        ("Saldo total", resumo.get("saldo_total", 0)),
        ("Consumo total no período", resumo.get("consumo_total_periodo", 0)),
    ]
    for row_index, (label, value) in enumerate(summary_rows, start=3):
        summary_sheet.cell(row=row_index, column=1, value=label)
        summary_sheet.cell(row=row_index, column=2, value=_stringify(value))

    def fill_sheet(sheet_name: str, columns: list[tuple[str, str]], rows: list[dict]):
        sheet = workbook.create_sheet(sheet_name)
        for column_index, (label, _) in enumerate(columns, start=1):
            cell = sheet.cell(row=1, column=column_index, value=label)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2563EB")
        for row_index, row in enumerate(rows, start=2):
            for column_index, (_, key) in enumerate(columns, start=1):
                sheet.cell(row=row_index, column=column_index, value=_stringify(row.get(key)))
        for column_index, (label, key) in enumerate(columns, start=1):
            values = [_stringify(row.get(key)) for row in rows]
            max_size = max([len(label)] + [len(value) for value in values] + [12])
            sheet.column_dimensions[get_column_letter(column_index)].width = min(max_size + 2, 36)

    fill_sheet(
        "Baixo Estoque",
        [("Referência", "referencia"), ("Descrição", "descricao"), ("Aplicação", "aplicacao_tipo"), ("Estoque", "quantidade_estoque"), ("Mínimo", "estoque_minimo"), ("Déficit", "deficit")],
        report.get("baixo_estoque", []),
    )
    fill_sheet(
        "Consumo",
        [("Referência", "referencia"), ("Descrição", "descricao"), ("Consumo", "consumo_total"), ("Último consumo", "ultimo_consumo")],
        report.get("consumo_periodo", []),
    )
    fill_sheet(
        "Ranking Top 5",
        [("Referência", "referencia"), ("Descrição", "descricao"), ("Consumo", "consumo_total"), ("Último consumo", "ultimo_consumo")],
        report.get("ranking_uso", []),
    )

    workbook.save(path)
    return path


def export_material_report_pdf(
    report: dict,
    *,
    output_path: str | Path,
    logo_path: str | Path | None = None,
    generated_by: str = "",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    periodo = report.get("periodo", {})
    resumo = report.get("resumo", {})
    subtitle = (
        f"Período {periodo.get('data_inicial') or '-'} a {periodo.get('data_final') or datetime.now().strftime('%Y-%m-%d')}"
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
    )

    story = _build_cover_page("Relatório de Estoque", subtitle, generated_by, logo_path, styles, landscape_mode=False)
    story.append(PageBreak())
    story.extend(_build_header("Relatório de Estoque", subtitle, generated_by, logo_path, styles))
    story.extend(
        _build_summary_cards(
            [
                ("Total de materiais", str(resumo.get("total_materiais", 0))),
                ("Abaixo do mínimo", str(resumo.get("abaixo_minimo", 0))),
                ("Saldo total", str(resumo.get("saldo_total", 0))),
                ("Consumo no período", str(resumo.get("consumo_total_periodo", 0))),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 10))

    sections = [
        (
            "Materiais abaixo do mínimo",
            [("Referência", "referencia"), ("Descrição", "descricao"), ("Aplicação", "aplicacao_tipo"), ("Estoque", "quantidade_estoque"), ("Mínimo", "estoque_minimo"), ("Déficit", "deficit")],
            report.get("baixo_estoque", []),
        ),
        (
            "Consumo no período",
            [("Referência", "referencia"), ("Descrição", "descricao"), ("Consumo", "consumo_total"), ("Último consumo", "ultimo_consumo")],
            report.get("consumo_periodo", []),
        ),
        (
            "Ranking Top 5",
            [("Referência", "referencia"), ("Descrição", "descricao"), ("Consumo", "consumo_total"), ("Último consumo", "ultimo_consumo")],
            report.get("ranking_uso", []),
        ),
    ]

    for title, columns, rows in sections:
        story.append(Paragraph(title, styles["section"]))
        story.append(Spacer(1, 4))
        if rows:
            table = Table(
                [[Paragraph(label, styles["table_header"]) for label, _ in columns]]
                + [
                    [Paragraph(_safe_paragraph_text(_stringify(row.get(key))), styles["table_cell"]) for _, key in columns]
                    for row in rows
                ],
                repeatRows=1,
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY_BLUE)),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT_BG)]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(table)
        else:
            story.append(Paragraph("Sem registros para esta seção.", styles["muted_box"]))
        story.append(Spacer(1, 10))

    story.extend(_build_signature_block(generated_by, styles))
    doc.build(
        story,
        onFirstPage=lambda canvas, document: _draw_footer(canvas, document, generated_by),
        onLaterPages=lambda canvas, document: _draw_footer(canvas, document, generated_by),
    )
    return path


def _build_header(title: str, subtitle: str, generated_by: str, logo_path: str | Path | None, styles):
    story = []
    cover_band = Table(
        [[Paragraph("Grupo Chibatão | Relatório corporativo", styles["cover_band"])]],
        colWidths=[180 * mm],
    )
    cover_band.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(MUTED)),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.45, colors.HexColor("#E2E8F0")),
            ]
        )
    )
    story.append(cover_band)
    story.append(Spacer(1, 6))

    header_row = []
    if logo_path and Path(logo_path).exists():
        header_row.append(Image(str(logo_path), width=22 * mm, height=14 * mm))
    else:
        header_row.append(Paragraph(" ", styles["body"]))
    header_row.append(Paragraph(f"<b>{title}</b><br/><font color='{MUTED}'>{subtitle}</font>", styles["title"]))

    metadata = [
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"Emitido por: {generated_by or 'Sistema'}",
        "Grupo Chibatão",
    ]
    header_row.append(Paragraph("<br/>".join(metadata), styles["meta"]))

    table = Table([header_row], colWidths=[28 * mm, 116 * mm, 45 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LINEBELOW", (0, 0), (-1, -1), 0.7, colors.HexColor("#D9E2EF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 8))
    return story


def _build_cover_page(
    title: str,
    subtitle: str,
    generated_by: str,
    logo_path: str | Path | None,
    styles,
    *,
    landscape_mode: bool,
):
    story = []
    width = 250 * mm if landscape_mode else 180 * mm

    top_band = Table(
        [[Paragraph("Relatório executivo | Grupo Chibatão", styles["cover_band_large"])]],
        colWidths=[width],
    )
    top_band.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(MUTED)),
                ("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.HexColor("#D9E2EF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(top_band)
    story.append(Spacer(1, 18))

    if logo_path and Path(logo_path).exists():
        story.append(Image(str(logo_path), width=34 * mm, height=22 * mm))
        story.append(Spacer(1, 14))

    story.append(Paragraph(title, styles["cover_title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(subtitle, styles["cover_subtitle"]))
    story.append(Spacer(1, 22))

    story.extend(
        _build_summary_cards(
            [
                ("Emitido por", generated_by or "Sistema"),
                ("Data", datetime.now().strftime("%d/%m/%Y")),
                ("Hora", datetime.now().strftime("%H:%M")),
            ],
            styles,
            compact=False,
        )
    )
    story.append(Spacer(1, 24))

    intro = Table(
        [[Paragraph(
            "Documento gerado para apoio gerencial, rastreabilidade operacional e evidências de manutenção da frota portuária.",
            styles["cover_intro"],
        )]],
        colWidths=[width],
    )
    intro.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (-1, -1), 0.7, colors.HexColor("#D9E2EF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(intro)
    return story


def _build_summary_cards(items: list[tuple[str, str]], styles, *, compact: bool = True):
    cells = []
    for label, value in items:
        width = 54 * mm if compact else 58 * mm
        accent = _summary_accent_for(label, value)
        card = Table(
            [[Paragraph(label, styles["summary_label"])], [Paragraph(_safe_paragraph_text(value), styles["summary_value"])]],
            colWidths=[width],
        )
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(accent["bg"])),
                    ("LINELEFT", (0, 0), (-1, -1), 1.1, colors.HexColor(accent["border"])),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        cells.append(card)
    wrapper_width = 60 * mm if compact else 62 * mm
    wrapper = Table([cells], colWidths=[wrapper_width] * len(cells))
    wrapper.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0, colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return [wrapper]


def _build_signature_block(generated_by: str, styles):
    label = generated_by or "Sistema"
    block = Table(
        [[Paragraph("Emitido por", styles["signature_label"])], [Paragraph(label, styles["signature_value"])]],
        colWidths=[70 * mm],
    )
    block.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 1), (-1, 1), 0.7, colors.HexColor("#94A3B8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [block]


def _activity_status_stamp(status_text: str, styles):
    normalized = status_text.lower()
    if "instalado" in normalized and "nao" not in normalized and "não" not in normalized:
        accent = {"bg": SEVERITY_GREEN_BG, "border": SEVERITY_GREEN, "text": SEVERITY_GREEN}
    elif "nao instalado" in normalized or "não instalado" in normalized:
        accent = {"bg": SEVERITY_RED_BG, "border": SEVERITY_RED, "text": SEVERITY_RED}
    else:
        accent = {"bg": SEVERITY_YELLOW_BG, "border": SEVERITY_YELLOW, "text": SEVERITY_YELLOW}

    stamp = Table([[Paragraph(_safe_paragraph_text(status_text.upper()), styles["stamp"])]] , colWidths=[42 * mm])
    stamp.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(accent["bg"])),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor(accent["border"])),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return stamp


def _build_chart_section(columns, rows, styles):
    metric_key, metric_label = _detect_metric_column(columns, rows)
    category_key, _ = _detect_category_column(columns)
    if not metric_key or not category_key:
        return []

    top_rows = sorted(rows, key=lambda row: _to_number(row.get(metric_key)), reverse=True)[:5]
    if not top_rows:
        return []

    max_value = max(_to_number(row.get(metric_key)) for row in top_rows) or 1
    drawing = Drawing(520, 150)
    base_y = 18
    bar_height = 18
    gap = 10
    drawing.add(String(0, 132, f"Gráfico executivo - {metric_label}", fontName="Helvetica-Bold", fontSize=11, fillColor=colors.HexColor(BRAND_BLUE)))

    for index, row in enumerate(top_rows):
        y = 104 - index * (bar_height + gap)
        value = _to_number(row.get(metric_key))
        width = 320 * (value / max_value)
        label = _stringify(row.get(category_key))[:28]
        severity = _severity_for_value(value, max_value)
        drawing.add(String(0, y + 4, label, fontName="Helvetica", fontSize=8.5, fillColor=colors.HexColor(BRAND_BLUE)))
        drawing.add(Rect(132, y, width, bar_height, fillColor=colors.HexColor(severity["color"]), strokeColor=colors.HexColor(severity["color"])))
        drawing.add(String(460, y + 4, str(int(value) if value.is_integer() else value), fontName="Helvetica-Bold", fontSize=8.5, fillColor=colors.HexColor(BRAND_BLUE)))

    wrapper = Table([[drawing]], colWidths=[170 * mm])
    wrapper.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E2EF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return [Paragraph("Gráfico visual", styles["section"]), wrapper]


def _build_top_five_section(columns, rows, styles):
    metric_key, metric_label = _detect_metric_column(columns, rows)
    category_key, category_label = _detect_category_column(columns)
    if not metric_key or not category_key:
        return []

    top_rows = sorted(rows, key=lambda row: _to_number(row.get(metric_key)), reverse=True)[:5]
    if not top_rows:
        return []

    table_data = [[
        Paragraph("Posição", styles["table_header"]),
        Paragraph(category_label, styles["table_header"]),
        Paragraph(metric_label, styles["table_header"]),
        Paragraph("Prioridade", styles["table_header"]),
    ]]
    row_backgrounds = []
    for index, row in enumerate(top_rows, start=1):
        severity = _severity_for_value(_to_number(row.get(metric_key)), _to_number(top_rows[0].get(metric_key)) or 1)
        row_backgrounds.append(colors.HexColor(severity["bg"]))
        table_data.append(
            [
                Paragraph(str(index), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(_stringify(row.get(category_key))), styles["table_cell"]),
                Paragraph(_safe_paragraph_text(_stringify(row.get(metric_key))), styles["table_cell"]),
                Paragraph(severity["label"], styles["table_cell"]),
            ]
        )

    table = Table(table_data, colWidths=[20 * mm, 88 * mm, 28 * mm, 30 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY_BLUE)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    for index, background in enumerate(row_backgrounds, start=1):
        table.setStyle(TableStyle([("BACKGROUND", (0, index), (-1, index), background)]))
    return [Paragraph("Ranking Top 5", styles["section"]), table]


def _build_executive_conclusion(columns, rows, styles, period_label: str | None):
    metric_key, metric_label = _detect_metric_column(columns, rows)
    category_key, category_label = _detect_category_column(columns)
    period_text = period_label or f"base consolidada até {datetime.now().strftime('%d/%m/%Y')}"
    if not rows or not metric_key or not category_key:
        conclusion = (
            f"Conclusão executiva: não foram identificados dados suficientes para análise consolidada no período {period_text}."
        )
        recommendation = "Prioridade sugerida: manter monitoramento e consolidar nova base antes de ações corretivas amplas."
        severity = {"bg": LIGHT_BG, "border": "#D9E2EF"}
    else:
        sorted_rows = sorted(rows, key=lambda row: _to_number(row.get(metric_key)), reverse=True)
        top_row = sorted_rows[0]
        total_metric = sum(_to_number(row.get(metric_key)) for row in rows)
        average_metric = total_metric / max(len(rows), 1)
        top_value = _to_number(top_row.get(metric_key))
        severity = _severity_for_value(top_value, top_value)
        priority_text = _overall_priority_label(columns, rows)
        conclusion = (
            f"Conclusão executiva: no período {period_text}, o indicador principal '{metric_label}' somou "
            f"{int(total_metric) if total_metric.is_integer() else round(total_metric, 2)}. "
            f"O maior destaque ficou em {category_label.lower()} '{_stringify(top_row.get(category_key))}', com "
            f"{int(_to_number(top_row.get(metric_key))) if _to_number(top_row.get(metric_key)).is_integer() else round(_to_number(top_row.get(metric_key)), 2)}. "
            f"A média por registro foi de {round(average_metric, 2)}."
        )
        recommendation = (
            f"Prioridade sugerida: {priority_text.lower()}. Direcionar a atuação imediata sobre "
            f"{category_label.lower()} '{_stringify(top_row.get(category_key))}' e acompanhar a evolução das demais ocorrências no mesmo período."
        )

    box = Table(
        [
            [Paragraph(_safe_paragraph_text(conclusion), styles["body"])],
            [Paragraph(_safe_paragraph_text(recommendation), styles["body"])],
        ],
        colWidths=[170 * mm],
    )
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(severity["bg"])),
                ("LINELEFT", (0, 0), (-1, -1), 1.1, colors.HexColor(severity["border"])),
                ("LINEBELOW", (0, -1), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return [Paragraph("Conclusão executiva", styles["section"]), box]


def _overall_priority_label(columns, rows) -> str:
    metric_key, _ = _detect_metric_column(columns, rows)
    if not rows or not metric_key:
        return "Monitoramento preventivo"
    max_value = max(_to_number(row.get(metric_key)) for row in rows) or 1
    severity = _severity_for_value(max_value, max_value)
    if severity["label"] == "Alta":
        return "Alta prioridade"
    if severity["label"] == "Moderada":
        return "Prioridade moderada"
    return "Cenário controlado"


def _summary_accent_for(label: str, value: str):
    text = f"{label} {value}".lower()
    if "semaforo executivo" in text or "semáforo executivo" in text:
        if "alta" in text:
            return {"bg": SEVERITY_RED_BG, "border": SEVERITY_RED}
        if "moderada" in text:
            return {"bg": SEVERITY_YELLOW_BG, "border": SEVERITY_YELLOW}
        return {"bg": SEVERITY_GREEN_BG, "border": SEVERITY_GREEN}
    return {"bg": "#FFFFFF", "border": "#D9E2EF"}


def _severity_for_value(value: float, max_value: float):
    ratio = 0 if max_value <= 0 else value / max_value
    if value <= 0:
        return {"label": "Controlada", "color": SEVERITY_GREEN, "bg": SEVERITY_GREEN_BG, "border": SEVERITY_GREEN}
    if ratio >= 0.67 or value >= 10:
        return {"label": "Alta", "color": SEVERITY_RED, "bg": SEVERITY_RED_BG, "border": SEVERITY_RED}
    if ratio >= 0.34 or value >= 4:
        return {"label": "Moderada", "color": SEVERITY_YELLOW, "bg": SEVERITY_YELLOW_BG, "border": SEVERITY_YELLOW}
    return {"label": "Controlada", "color": SEVERITY_GREEN, "bg": SEVERITY_GREEN_BG, "border": SEVERITY_GREEN}


def _detect_metric_column(columns, rows):
    preferred = ["total_nc", "nc", "abertas", "resolvidas"]
    labels = dict(columns)
    for key in preferred:
        if any(column_key == key for _, column_key in columns):
            return key, next(label for label, column_key in columns if column_key == key)
    for label, key in columns:
        if rows and any(_is_number(row.get(key)) for row in rows):
            return key, label
    return None, None


def _detect_category_column(columns):
    preferred = ["item_nome", "item", "frota", "modelo"]
    for key in preferred:
        for label, column_key in columns:
            if column_key == key:
                return column_key, label
    if columns:
        return columns[0][1], columns[0][0]
    return None, None


def _is_number(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _to_number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _draw_footer(canvas, document, generated_by: str):
    canvas.saveState()
    footer_y = 9 * mm
    width = document.pagesize[0] - document.leftMargin - document.rightMargin
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(document.leftMargin, footer_y + 4 * mm, document.leftMargin + width, footer_y + 4 * mm)
    canvas.setFillColor(colors.HexColor(MUTED))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(document.leftMargin, footer_y, "Grupo Chibatão • Sistema de Checklist de Frota")
    canvas.drawCentredString(document.leftMargin + width / 2, footer_y, f"Emitido por: {generated_by or 'Sistema'}")
    canvas.drawRightString(document.leftMargin + width, footer_y, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


def _key_value_table(rows: list[list[str]], styles):
    table = Table(
        [[Paragraph(f"<b>{label}</b>", styles["body"]), Paragraph(_safe_paragraph_text(value), styles["body"])] for label, value in rows],
        colWidths=[48 * mm, 122 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#FBFDFF")]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _reportlab_image(raw_bytes: bytes, width: float, height: float):
    buffer = io.BytesIO(raw_bytes)
    image = Image(buffer, width=width, height=height, kind="proportional")
    image.hAlign = "CENTER"
    return image


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleBlock",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=15,
            leading=19,
            textColor=colors.HexColor(BRAND_BLUE),
        ),
        "meta": ParagraphStyle(
            "MetaBlock",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor(MUTED),
            alignment=2,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor(BRAND_BLUE),
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.HexColor(BRAND_BLUE),
            spaceAfter=4,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.3,
            leading=10,
            textColor=colors.HexColor(BRAND_BLUE),
        ),
        "muted_box": ParagraphStyle(
            "MutedBox",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            alignment=1,
            textColor=colors.HexColor(MUTED),
        ),
        "cover_band": ParagraphStyle(
            "CoverBand",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor(MUTED),
        ),
        "cover_band_large": ParagraphStyle(
            "CoverBandLarge",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=colors.HexColor(MUTED),
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor(BRAND_BLUE),
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor(MUTED),
        ),
        "cover_intro": ParagraphStyle(
            "CoverIntro",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor(BRAND_BLUE),
        ),
        "summary_label": ParagraphStyle(
            "SummaryLabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor(MUTED),
        ),
        "summary_value": ParagraphStyle(
            "SummaryValue",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor(BRAND_BLUE),
        ),
        "signature_label": ParagraphStyle(
            "SignatureLabel",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor(MUTED),
        ),
        "signature_value": ParagraphStyle(
            "SignatureValue",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor(BRAND_BLUE),
        ),
        "stamp": ParagraphStyle(
            "Stamp",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=1,
            textColor=colors.HexColor(BRAND_BLUE),
        ),
    }


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    return str(value)


def _activity_item_status_text(value: str | None) -> str:
    return {
        "PENDENTE": "Pendente",
        "INSTALADO": "Instalado",
        "NAO_INSTALADO": "Não instalado",
    }.get(value or "", value or "-")


def _format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    try:
        text = value.replace("Z", "")
        return datetime.fromisoformat(text).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def _safe_paragraph_text(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
