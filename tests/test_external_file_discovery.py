from __future__ import annotations

import tempfile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.inventory_import_service import discover_inventory_file
from app.services.wash_service import discover_wash_file


def test_inventory_discovery_ignores_external_configured_file():
    external_file = Path(tempfile.gettempdir()) / "INVENTARIO FROTA 2026.xlsx"
    external_file.write_bytes(b"fake")
    try:
        assert discover_inventory_file(str(external_file)) is None
    finally:
        external_file.unlink(missing_ok=True)


def test_wash_discovery_ignores_external_configured_file():
    external_file = Path(tempfile.gettempdir()) / "CONTROLE_DE_LAVAGEM.xlsx"
    external_file.write_bytes(b"fake")
    try:
        assert discover_wash_file(str(external_file)) is None
    finally:
        external_file.unlink(missing_ok=True)
