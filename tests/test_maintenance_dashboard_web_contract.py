from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = PROJECT_ROOT / "web_app" / "index.html"
DASHBOARD_PATH = PROJECT_ROOT / "web_app" / "dashboard-manutencao" / "index.html"
DASHBOARD_JS_PATH = PROJECT_ROOT / "web_app" / "static" / "js" / "maintenance-dashboard.js"
TV_DASHBOARD_PATH = PROJECT_ROOT / "web_app" / "dashboard-manutencao" / "tv" / "index.html"
TV_DASHBOARD_JS_PATH = PROJECT_ROOT / "web_app" / "static" / "js" / "maintenance-dashboard-tv.js"


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
        self.assertIn('id="dashboard-access-state" class="dashboard-state-card hidden"', dashboard_html)
        self.assertIn('class="dashboard-header-actions"', dashboard_html)
        self.assertIn('href="./?modo=gestao-os"', dashboard_html)
        self.assertIn('Gestão de OS', dashboard_html)
        self.assertIn("get(\"modo\") === \"gestao-os\"", dashboard_js)
        self.assertIn('includes(String(dashboardState.user?.tipo || "").toLowerCase())', dashboard_js)
        self.assertIn("dashboardElements.accessState.classList.add(\"hidden\")", dashboard_js)
        self.assertIn("redirectToDashboardLogin", dashboard_js)
        self.assertIn("localStorage.removeItem(\"sessionLastActivityAt\")", dashboard_js)
        self.assertIn("currentLocalApi", dashboard_js)
        self.assertIn("onrender\\.com|vercel\\.app", dashboard_js)

    def test_mobile_menu_links_dashboard_only_after_authenticated_app_renders(self):
        index_html = INDEX_PATH.read_text(encoding="utf-8")
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="open-maintenance-dashboard-menu"', index_html)
        self.assertIn("openMaintenanceDashboardMenu", app_js)
        self.assertIn('window.location.href = "./dashboard-manutencao/"', app_js)
        self.assertIn("canViewMaintenanceDashboard", app_js)

    def test_tv_dashboard_opens_without_access_code(self):
        dashboard_html = DASHBOARD_PATH.read_text(encoding="utf-8")
        dashboard_js = DASHBOARD_JS_PATH.read_text(encoding="utf-8")
        tv_html = TV_DASHBOARD_PATH.read_text(encoding="utf-8")
        tv_js = TV_DASHBOARD_JS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("tv-access-token", tv_html)
        self.assertIn("maintenance-dashboard-tv.js", tv_html)
        self.assertIn("/dashboard-manutencao/tv/dados", tv_js)
        self.assertNotIn('"X-Dashboard-TV-Token"', tv_js)
        self.assertNotIn("sessionStorage", tv_js)
        self.assertIn('new URLSearchParams(window.location.search).get("api")', tv_js)
        self.assertIn("TV_REFRESH_MS", tv_js)
        self.assertIn('id="dashboard-open-tv"', dashboard_html)
        self.assertNotIn("dashboard-tv-access-create", dashboard_html)
        self.assertNotIn("/dashboard-manutencao/tv/acessos", dashboard_js)


if __name__ == "__main__":
    unittest.main()
