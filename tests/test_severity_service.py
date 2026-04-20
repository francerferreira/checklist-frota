from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

from services.severity_service import overall_executive_status, severity_from_counts, severity_from_occurrence


class SeverityServiceTests(unittest.TestCase):
    def test_severity_from_counts_high(self):
        result = severity_from_counts(12, 3)
        self.assertEqual(result["label"], "Alta")

    def test_severity_from_counts_moderate(self):
        result = severity_from_counts(5, 1)
        self.assertEqual(result["label"], "Moderada")

    def test_severity_from_occurrence_controlled_when_resolved(self):
        result = severity_from_occurrence({"resolvido": True})
        self.assertEqual(result["label"], "Controlada")

    def test_overall_executive_status_high_priority(self):
        result = overall_executive_status([{"total_nc": 12, "abertas": 4}], total=12, open_total=4)
        self.assertEqual(result["label"], "Alta prioridade")


if __name__ == "__main__":
    unittest.main()
