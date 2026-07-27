from pathlib import Path
import unittest

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
import sys
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.routes.stops_dashboard_tv import bp
from app.services.stops_dashboard_tv_service import _daily_slices, _projection_row, _target_row


SERVICE = BACKEND / "app" / "services" / "stops_dashboard_tv_service.py"
TARGETS = BACKEND / "stop_dashboard_targets.json"


class DashboardTvStopsApiContractTest(unittest.TestCase):
    def test_independent_read_only_routes_exist(self):
        app = Flask(__name__)
        app.register_blueprint(bp)
        routes = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/api/dashboard-tv/paradas", routes)
        self.assertIn("/dashboard-tv/paradas", routes)

    def test_service_uses_existing_status_events_and_scopes_lbs_rtg(self):
        source = SERVICE.read_text(encoding="utf-8")
        self.assertIn('STOP_FAMILY_CODES = ("lbs", "rtg")', source)
        self.assertIn("EquipmentStatusEvent", source)
        self.assertIn('"active_stops"', source)
        self.assertIn('"daily_trend"', source)
        self.assertIn('"targets"', source)
        self.assertIn('"monthly_summary"', source)
        self.assertIn('"projections"', source)
        self.assertTrue(TARGETS.exists())

    def test_target_status_follows_visual_thresholds(self):
        self.assertEqual(_target_row("lbs-pier", 7, {"lbs-pier": 10}, [])["status"], "NORMAL")
        self.assertEqual(_target_row("lbs-pier", 8, {"lbs-pier": 10}, [])["status"], "ATENCAO")
        self.assertEqual(_target_row("lbs-pier", 9.5, {"lbs-pier": 10}, [])["status"], "VERMELHO")
        self.assertEqual(_target_row("lbs-pier", 11, {"lbs-pier": 10}, [])["status"], "CRITICO")

    def test_daily_slices_split_a_stop_at_midnight(self):
        from datetime import datetime

        row = {"started_at": "2026-07-31T22:00:00", "ended_at": "2026-08-01T04:00:00"}
        self.assertEqual(
            _daily_slices(row, datetime(2026, 7, 31), datetime(2026, 8, 1, 4)),
            [("2026-07-31", 2.0), ("2026-08-01", 4.0)],
        )

    def test_projection_is_calculated_from_elapsed_days(self):
        projection = _projection_row("lbs-pier", 5, {"lbs-pier": 10}, 5, 10, True)
        self.assertEqual(projection["projected_hours"], 10.0)
        self.assertEqual(projection["percentage"], 100.0)
        self.assertEqual(projection["status"], "VERMELHO")


if __name__ == "__main__":
    unittest.main()
