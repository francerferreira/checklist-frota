from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.services.inventory_import_service import replace_portuary_inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Substitui o cadastro ativo pelo inventario portuario CSV.")
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    path = args.csv_path.expanduser().resolve()
    if not path.is_file():
        parser.error(f"Arquivo nao encontrado: {path}")

    app = create_app()
    with app.app_context():
        result = replace_portuary_inventory(path)
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
