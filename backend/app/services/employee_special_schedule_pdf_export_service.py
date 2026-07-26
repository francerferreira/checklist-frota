from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_DIR = PROJECT_ROOT / "desktop"
if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_DIR))

from services.export_service import export_rows_to_pdf  # noqa: E402


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
