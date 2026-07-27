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

from ui.preventive_family_page import PreventiveLBSPage, PreventiveRTGPage


class FakePreventiveAPI:
    def __init__(self):
        self.user = {"login": "admin", "nome": "Administrador", "tipo": "admin"}
        self.recorded = []

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

    def record_equipment_hourmeter(self, vehicle_id, payload):
        self.recorded.append((vehicle_id, payload))
        return {"id": 99, "vehicle_id": vehicle_id, "reading": payload["reading"]}


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

    def test_lbs_screen_reuses_same_preventive_structure(self):
        page = PreventiveLBSPage(FakePreventiveAPI())
        page.refresh()

        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 1).text(), "LBS 03")
        self.assertEqual(page.cards["total"].value_label.text(), "1")
        self.assertEqual(page.cards["SEM_DADOS"].value_label.text(), "1")
        page.close()

    def test_hourmeter_dialog_saves_selected_family_equipment(self):
        api = FakePreventiveAPI()
        page = PreventiveRTGPage(api)
        page.refresh()
        from ui.preventive_family_page import HourmeterEntryDialog

        dialog = HourmeterEntryDialog(api, "RTG", page.rows)
        dialog.reading_spin.setValue(20350)
        dialog._save()

        self.assertEqual(len(api.recorded), 1)
        self.assertEqual(api.recorded[0][0], 1)
        self.assertEqual(api.recorded[0][1]["reading"], 20350)
        self.assertEqual(api.recorded[0][1]["notes"], None)
        dialog.close()
        page.close()


if __name__ == "__main__":
    unittest.main()
