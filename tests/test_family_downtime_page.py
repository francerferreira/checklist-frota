from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

from PySide6.QtWidgets import QApplication

from ui.family_downtime_page import FamilyDowntimePage, _hours_for_events


class FakeDowntimeAPI:
    def __init__(self):
        now = datetime.now().replace(microsecond=0)
        self.rows = [
            {
                "vehicle": {
                    "id": 10,
                    "frota": "RTG 01",
                    "tipo": "RTG",
                    "modelo": "RTG",
                    "operational_state": {
                        "operational_status": "INDISPONIVEL",
                        "status_reason": "Falha eletrica",
                    },
                },
                "family": {"code": "RTG", "name": "RTG"},
                "location": {"full_name": "ATR / Patio 01"},
            },
            {
                "vehicle": {
                    "id": 20,
                    "frota": "LBS 01",
                    "tipo": "LBS",
                    "operational_state": {"operational_status": "DISPONIVEL"},
                },
                "family": {"code": "LBS", "name": "LBS"},
                "location": {"full_name": "Pier / Berco 01"},
            },
        ]
        self.histories = {
            10: [{
                "status": "INDISPONIVEL",
                "started_at": (now - timedelta(hours=2)).isoformat(),
                "ended_at": None,
                "reason": "Falha eletrica",
            }],
            20: [],
        }

    def get_availability_overview(self, **_kwargs):
        return {"rows": self.rows}

    def get_equipment_status_history(self, vehicle_id):
        return self.histories.get(vehicle_id, [])


class FamilyDowntimePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_page_filters_by_family_and_calculates_stop_hours(self):
        page = FamilyDowntimePage(FakeDowntimeAPI(), "RTG", {"login": "admin"})
        page.refresh()
        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 0).text(), "RTG 01")
        self.assertEqual(page.table.item(0, 2).text(), "Indisponivel")
        self.assertGreater(float(page.table.item(0, 4).text().split()[0]), 0)
        page.close()

    def test_event_hours_respect_period_overlap(self):
        now = datetime.now().replace(microsecond=0)
        events = [{
            "status": "MANUTENCAO",
            "started_at": (now - timedelta(hours=5)).isoformat(),
            "ended_at": (now - timedelta(hours=3)).isoformat(),
        }]
        value = _hours_for_events(events, now - timedelta(hours=4), now)
        self.assertEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()
