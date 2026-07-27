from __future__ import annotations

from pathlib import Path

from desktop.services.export_service import export_rows_to_csv, export_rows_to_pdf, export_rows_to_xlsx


COLUMNS = [
    ("Família", "familia"),
    ("Equipamento", "equipamento"),
    ("Situação", "situacao"),
]
ROWS = [
    {"familia": "RTG", "equipamento": "RTG 02", "situacao": "Atenção"},
    {"familia": "LBS", "equipamento": "LBS 03", "situacao": "No prazo"},
]


def test_preventive_exports_keep_headers_and_rows(tmp_path: Path):
    csv_path = export_rows_to_csv(COLUMNS, ROWS, tmp_path / "preventivas.csv")
    xlsx_path = export_rows_to_xlsx("Preventivas RTG", COLUMNS, ROWS, tmp_path / "preventivas.xlsx")
    pdf_path = export_rows_to_pdf(
        "Preventivas RTG",
        "Visão filtrada",
        COLUMNS,
        ROWS,
        tmp_path / "preventivas.pdf",
        period_label="Família RTG",
    )

    assert csv_path.read_text(encoding="utf-8-sig").splitlines() == [
        "Família;Equipamento;Situação",
        "RTG;RTG 02;Atenção",
        "LBS;LBS 03;No prazo",
    ]
    assert xlsx_path.exists() and xlsx_path.stat().st_size > 0
    assert pdf_path.exists() and pdf_path.stat().st_size > 0

