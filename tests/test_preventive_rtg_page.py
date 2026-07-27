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

from ui.preventive_family_page import PreventiveRTGPage


class FakePreventiveAPI:
    def get_equipment(self, tipo=None, ativos=None):
        return [
            {
                "id": 1,
                "ativo": True,
                "tipo": "RTG",
                "frota": "RTG 02",
                "modelo": "RTG Konecranes",
                "family": {"code": "rtg", "name": "RTG"},
                "operational_location": {"full_name": "ATR / Pátio 01"},
                "operational_state": {"latest_hourmeter": 20320, "latest_hourmeter_at": "2026-07-26T12:00:00"},
            },
            {
                "id": 2,
                "ativo": True,
                "tipo": "LBS",
                "frota": "LBS 03",
                "family": {"code": "lbs", "name": "LBS"},
            },
        ]

    def get_preventive_plans(self):
        return [
            {
                "id": 10,
                "vehicle_id": 1,
                "status": "ATIVO",
                "title": "Preventiva RTG 500 h",
                "due": {
                    "calculation_status": "ATENCAO",
                    "next_due_hourmeter": 20500,
                    "hours_remaining": 180,
                    "percent_used": 64,
                },
            }
        ]


class PreventiveRTGPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_rtg_screen_filters_family_and_exposes_due_state(self):
        page = PreventiveRTGPage(FakePreventiveAPI())
        page.refresh()

        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 1).text(), "RTG 02")
        self.assertEqual(page.table.item(0, 0).text(), "Atenção")
        self.assertEqual(page.cards["total"].value_label.text(), "1")
        self.assertEqual(page.cards["ATENCAO"].value_label.text(), "1")
        self.assertIn("RTG 02", page.detail_labels["equipment"].text())
        self.assertIn("180", page.detail_labels["remaining"].text())
        page.close()


if __name__ == "__main__":
    unittest.main()
