from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_DIR = PROJECT_ROOT / "desktop"
if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_DIR))

from services.wash_reporting_service import export_wash_month_pdf  # noqa: E402


def export_monthly_wash_pdf(overview: dict, output_path: str | Path, generated_by: str = "") -> Path:
logo_path = DESKTOP_DIR / "assets" / "app-logo-cover.png"
    return export_wash_month_pdf(
        overview,
        output_path=output_path,
        logo_path=logo_path if logo_path.exists() else None,
        generated_by=generated_by,
    )
