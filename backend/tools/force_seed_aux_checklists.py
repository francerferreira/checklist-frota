from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.models import ChecklistCatalogItem
from app.services.runtime_schema_service import ensure_runtime_schema
from app.services.seed_service import seed_reference_data


def main() -> int:
    app = create_app()
    with app.app_context():
        ensure_runtime_schema()
        seed_reference_data()
        rows = ChecklistCatalogItem.query.filter_by(ativo=True).all()
        counts = Counter(row.vehicle_type for row in rows)
        print("CHECKLIST_ATIVO_POR_TIPO")
        for vehicle_type in sorted(counts):
            print(f"{vehicle_type}={counts[vehicle_type]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
