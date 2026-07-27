from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

from PySide6.QtWidgets import QApplication

from ui.family_operational_page import FamilyOperationalPage


class FakeOperationalAPI:
    def get_availability_overview(self):
        return {
            "rows": [
                {
                    "vehicle": {
                        "id": 1,
                        "frota": "RTG 02",
                        "tipo": "RTG",
                        "operational_state": {
                            "operational_status": "DISPONIVEL",
                            "latest_hourmeter": 1250.5,
                            "status_reason": None,
                        },
                    },
                    "family": {"code": "rtg", "name": "RTG"},
                    "location": {
                        "full_name": "ATR / Patio 01",
                        "parent_name": "ATR",
                        "name": "Patio 01",
                    },
                    "availability_percentage": 96.5,
                },
                {
                    "vehicle": {
                        "id": 2,
                        "frota": "LBS 02",
                        "tipo": "LBS",
                        "operational_state": {"operational_status": "MANUTENCAO"},
                    },
                    "family": {"code": "lbs", "name": "LBS"},
                    "location": {"full_name": "Berco 01"},
                    "availability_percentage": 0,
                },
            ]
        }


class FamilyOperationalPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_rtg_panel_separates_family_area_and_patio(self):
        page = FamilyOperationalPage(FakeOperationalAPI(), "RTG", "rtg_downtime")
        page.refresh()
        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 0).text(), "ATR")
        self.assertEqual(page.table.item(0, 1).text(), "Patio 01")
        self.assertEqual(page.table.item(0, 2).text(), "RTG 02")
        self.assertEqual(page.available_card.value_label.text(), "1")
        page.close()


if __name__ == "__main__":
    unittest.main()
