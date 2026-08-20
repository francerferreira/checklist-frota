"""Carrega a base mestre Markdown no banco local/configurado."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa Serviços, Materiais e histórico SC-PC-NF.")
    parser.add_argument("--source", required=True, help="Caminho do BASE_SERVICOS_MATERIAIS_COMPRAS.md")
    parser.add_argument("--user-id", type=int, default=1, help="Usuário responsável pela importação (padrão: 1)")
    args = parser.parse_args()
    os.environ.setdefault("CHECKLIST_ALLOW_SQLITE", "1")
    os.environ.setdefault("CHECKLIST_FORCE_LOCAL_DB", "1")
    from app import create_app
    from app.services.purchase_markdown_import_service import import_purchase_markdown

    app = create_app()
    with app.app_context():
        result = import_purchase_markdown(args.source, user_id=args.user_id)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
