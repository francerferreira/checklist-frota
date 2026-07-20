from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = PROJECT_ROOT / "web_app" / "index.html"
DASHBOARD_PATH = PROJECT_ROOT / "web_app" / "dashboard-manutencao" / "index.html"
DASHBOARD_JS_PATH = PROJECT_ROOT / "web_app" / "static" / "js" / "maintenance-dashboard.js"


class MaintenanceDashboardWebContractTests(unittest.TestCase):
    def test_dashboard_has_own_static_route_and_real_data_endpoints(self):
        dashboard_html = DASHBOARD_PATH.read_text(encoding="utf-8")
        dashboard_js = DASHBOARD_JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Dashboard Operacional de Manutenção", dashboard_html)
        self.assertIn("maintenance-dashboard.js", dashboard_html)
        self.assertIn("/dashboard-manutencao/resumo", dashboard_js)
        self.assertIn("/dashboard-manutencao/graficos", dashboard_js)
        self.assertIn("/dashboard-manutencao/ativos-criticos", dashboard_js)
        self.assertIn("SEM DADOS", dashboard_js)
        self.assertIn("dashboard-operational-status-chart", dashboard_html)
        self.assertIn("dashboard-operational-trend", dashboard_html)
        self.assertIn("dashboard-performance", dashboard_html)

    def test_mobile_menu_links_dashboard_only_after_authenticated_app_renders(self):
        index_html = INDEX_PATH.read_text(encoding="utf-8")
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="open-maintenance-dashboard-menu"', index_html)
        self.assertIn("openMaintenanceDashboardMenu", app_js)
        self.assertIn('window.location.href = "./dashboard-manutencao/"', app_js)
        self.assertIn("canViewMaintenanceDashboard", app_js)


if __name__ == "__main__":
    unittest.main()
