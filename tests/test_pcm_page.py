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

from ui.pcm_page import PreventivePlanDialog


class PreventivePlanDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = PreventivePlanDialog(
            [{"id": 12, "frota": "RTG-12", "ativo": True}],
            [],
        )

    def tearDown(self):
        self.dialog.close()

    def test_calendar_payload_includes_tolerance_and_duration(self):
        self.dialog.title.setText("Lubrificação mensal")
        self.dialog.description.setText("Inspecionar e lubrificar os pontos definidos.")
        self.dialog.interval_days.setValue(30)
        self.dialog.tolerance_days.setValue(2)
        self.dialog.estimated_duration_minutes.setValue(90)

        payload = self.dialog.payload()

        self.assertEqual(payload["trigger_type"], "CALENDARIO")
        self.assertEqual(payload["tolerance_days"], 2)
        self.assertEqual(payload["estimated_duration_minutes"], 90)
        self.assertNotIn("interval_hourmeter", payload)

    def test_hourmeter_payload_excludes_calendar_fields(self):
        self.dialog.trigger.setCurrentIndex(1)
        self.dialog.title.setText("Revisão por horímetro")
        self.dialog.interval_hourmeter.setText("250")
        self.dialog.next_due_hourmeter.setText("1250")
        self.dialog.tolerance_hourmeter.setValue(12.5)

        payload = self.dialog.payload()

        self.assertEqual(payload["trigger_type"], "HORIMETRO")
        self.assertEqual(payload["tolerance_hourmeter"], 12.5)
        self.assertNotIn("interval_days", payload)
        self.assertFalse(self.dialog.interval_days.isEnabled())


if __name__ == "__main__":
    unittest.main()
