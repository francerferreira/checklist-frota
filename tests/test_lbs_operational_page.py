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

from ui.lbs_operational_page import LBSOperationalPage


class FakeLBSAPI:
    def get_availability_overview(self):
        return {
            "rows": [
                {
                    "vehicle": {
                        "id": 10,
                        "frota": "LBS 03",
                        "tipo": "LBS",
                        "serial_number": "141714",
                        "operational_state": {
                            "operational_status": "DISPONIVEL",
                            "latest_hourmeter": 810.25,
                            "status_reason": None,
                        },
                    },
                    "family": {"code": "lbs", "name": "LBS"},
                    "location": {
                        "full_name": "Pier Alfandegado / Berco 02",
                        "parent_name": "Pier Alfandegado",
                        "name": "Berco 02",
                    },
                    "availability_percentage": 98.0,
                },
                {
                    "vehicle": {
                        "id": 11,
                        "frota": "LBS 14",
                        "tipo": "LBS",
                        "serial_number": "141192",
                        "operational_state": {"operational_status": "MANUTENCAO"},
                    },
                    "family": {"code": "lbs", "name": "LBS"},
                    "location": {
                        "full_name": "Pier Provisorio / Itacoatiara",
                        "parent_name": "Pier Provisorio / Itacoatiara",
                        "name": "Pier Provisorio / Itacoatiara",
                    },
                    "availability_percentage": 0,
                },
                {
                    "vehicle": {"id": 12, "frota": "RTG 01", "tipo": "RTG"},
                    "family": {"code": "rtg", "name": "RTG"},
                    "location": {"full_name": "Alfandegado / Patio 01"},
                },
            ]
        }

    def get_equipment_links(self, *, active=None, parent_id=None, child_id=None):
        return [
            {
                "parent_vehicle_id": 10,
                "child_vehicle_id": 20,
                "link_type": "ACOPLADO",
                "active": True,
                "parent_equipment": {"id": 10, "frota": "LBS 03"},
                "child_equipment": {"id": 20, "frota": "Spreader 02", "tipo": "spreader"},
            },
            {
                "parent_vehicle_id": 10,
                "child_vehicle_id": 21,
                "link_type": "RESERVA",
                "active": True,
                "parent_equipment": {"id": 10, "frota": "LBS 03"},
                "child_equipment": {"id": 21, "frota": "Reserva 01", "tipo": "spreader"},
            },
        ]


class LBSOperationalPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_organizes_lbs_by_pier_berco_and_links(self):
        page = LBSOperationalPage(FakeLBSAPI(), "lbs_downtime")
        page.refresh()
        self.assertEqual(page.table.rowCount(), 2)
        self.assertEqual(page.table.item(0, 0).text(), "Píer Alfandegado")
        self.assertEqual(page.table.item(0, 1).text(), "Berco 02")
        self.assertEqual(page.table.item(0, 2).text(), "LBS 03")
        self.assertIn("Spreader 02", page.table.item(0, 4).text())
        self.assertIn("Reserva 01", page.table.item(0, 5).text())
        self.assertEqual(page.available_card.value_label.text(), "1")
        self.assertEqual(page.stopped_card.value_label.text(), "1")
        page.close()


if __name__ == "__main__":
    unittest.main()
