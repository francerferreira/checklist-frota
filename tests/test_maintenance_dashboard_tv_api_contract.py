from pathlib import Path
import sys
import unittest

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.routes.maintenance_dashboard_tv import bp


SERVICE = ROOT / "backend" / "app" / "services" / "maintenance_dashboard_tv_service.py"


class MaintenanceDashboardTvApiContractTest(unittest.TestCase):
    def test_independent_read_only_routes_exist(self):
        app = Flask(__name__)
        app.register_blueprint(bp)
        routes = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/api/dashboard-tv/manutencao", routes)
        self.assertIn("/dashboard-tv/manutencao", routes)

    def test_service_is_consolidated_for_lbs_and_rtg(self):
        source = SERVICE.read_text(encoding="utf-8")
        self.assertIn('TV_FAMILY_CODES = ("lbs", "rtg")', source)
        self.assertIn('"equipment_total"', source)
        self.assertIn('"critical_equipment"', source)
        self.assertIn('"materials_blocked"', source)
        self.assertIn('"action_plans"', source)


if __name__ == "__main__":
    unittest.main()
