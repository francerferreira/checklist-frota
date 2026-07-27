from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "web_app" / "dashboard-tv" / "manutencao" / "index.html"
CSS = ROOT / "web_app" / "static" / "css" / "dashboard-tv-maintenance.css"
JS = ROOT / "web_app" / "static" / "js" / "dashboard-tv-maintenance.js"


class MaintenanceDashboardTvShellContractTest(unittest.TestCase):
    def test_independent_four_page_shell_exists(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn("DASHBOARD TV — MANUTENÇÃO", html)
        self.assertEqual(html.count('data-tv-page='), 4)
        self.assertIn("dashboard-tv-maintenance.css", html)
        self.assertIn("dashboard-tv-maintenance.js", html)

    def test_shell_respects_tv_navigation_contract(self):
        css = CSS.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn("overflow: hidden", css)
        self.assertIn("grid-template-columns: repeat(12", css)
        self.assertIn("width: 400%", css)
        self.assertIn("ROTATION_MS = 40 * 1000", js)
        self.assertIn("REFRESH_MS = 60 * 1000", js)
        self.assertIn("PAUSE_AFTER_MANUAL_MS = 60 * 1000", js)
        self.assertNotIn("window.location.reload", js)
        self.assertIn("ArrowRight", js)
        self.assertIn("PageDown", js)


if __name__ == "__main__":
    unittest.main()
