from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_DIR = PROJECT_ROOT / "desktop"
if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_DIR))

from services.export_service import export_rows_to_pdf  # noqa: E402


def export_maintenance_pdf(payload: dict, output_path: str | Path, generated_by: str = "") -> Path:
    logo_path = DESKTOP_DIR / "assets" / "logo_grupo.png"
    return export_rows_to_pdf(
        payload["title"],
        payload["subtitle"],
        payload["columns"],
        payload["rows"],
        output_path,
        logo_path=logo_path if logo_path.exists() else None,
        generated_by=generated_by,
        period_label=payload.get("period_label"),
    )
