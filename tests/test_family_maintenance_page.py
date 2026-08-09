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

from PySide6.QtWidgets import QApplication, QPushButton

from ui.family_maintenance_page import FamilyMaintenancePage


class FakeMaintenanceAPI:
    def get_equipment(self, **kwargs):
        return []

    def get_maintenance_overview(self, year, month):
        return {
            "itens": [
                {
                    "scheduled_date": f"{year:04d}-{month:02d}-12",
                    "vehicle": {"id": 1, "frota": "RTG 02", "tipo": "RTG", "family": {"code": "rtg"}},
                    "schedule": {"title": "Inspeção preventiva RTG"},
                    "status": "PROGRAMADO",
                    "assigned_mechanic": {"nome": "Equipe RTG"},
                    "work_order": {"order_number": "OS-RTG-01", "status": "PROGRAMADA"},
                },
                {
                    "scheduled_date": f"{year:04d}-{month:02d}-13",
                    "vehicle": {"id": 2, "frota": "LBS 03", "tipo": "LBS", "family": {"code": "lbs"}},
                    "schedule": {"title": "Manutenção LBS"},
                    "status": "INSTALADO",
                    "assigned_mechanic": {"nome": "Equipe LBS"},
                    "work_order": None,
                },
            ]
        }


class FamilyMaintenancePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_filters_items_by_family_and_counts_orders(self):
        page = FamilyMaintenancePage(FakeMaintenanceAPI(), "RTG")
        page.refresh()
        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 1).text(), "RTG 02")
        self.assertEqual(page.table.item(0, 2).text(), "Corretiva")
        self.assertEqual(page.table.item(0, 4).text(), "Programado")
        self.assertEqual(page.table.item(0, 6).text(), "OS-RTG-01")
        self.assertEqual(page.corrective_card.value_label.text(), "1")
        self.assertEqual(page.findChild(type(page.corrective_card.value_label), "PageTitle").text(), "CORRETIVAS RTG")
        self.assertIn("Nova corretiva programada", [button.text() for button in page.findChildren(QPushButton)])
        page.close()


if __name__ == "__main__":
    unittest.main()
