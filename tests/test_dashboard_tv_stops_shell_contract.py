from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "web_app" / "dashboard-tv" / "paradas" / "index.html"
CSS = ROOT / "web_app" / "static" / "css" / "dashboard-tv-stops.css"
JS = ROOT / "web_app" / "static" / "js" / "dashboard-tv-stops.js"


class DashboardTvStopsShellContractTest(unittest.TestCase):
    def test_independent_four_page_shell(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertEqual(html.count('data-stops-page='), 4)
        self.assertIn("DASHBOARD TV", html)
        self.assertIn("CONTROLE DE PARADAS", html)
        self.assertIn("dashboard-tv-stops.css", html)
        self.assertIn("dashboard-tv-stops.js", html)

    def test_tv_layout_and_rotation_contract(self):
        css = CSS.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn("width: 100vw", css)
        self.assertIn("height: 100vh", css)
        self.assertIn("overflow: hidden", css)
        self.assertIn("width: 400%", css)
        self.assertIn("ROTATION_MS = 40 * 1000", js)
        self.assertIn("REFRESH_MS = 60 * 1000", js)
        self.assertIn("PAUSE_AFTER_MANUAL_MS = 60 * 1000", js)
        self.assertNotIn("window.location.reload", js)
        self.assertIn("ArrowRight", js)
        self.assertIn("PageDown", js)

    def test_visual_data_blocks_are_present(self):
        html = HTML.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn('data-stop-chart="offenders"', html)
        self.assertIn('data-stop-list="history-summary"', html)
        self.assertIn('data-stop-projection="rtg-total"', html)
        self.assertIn("status-critical", css)
        self.assertIn("statusLabel", js)
        self.assertIn("projected_hours", js)


if __name__ == "__main__":
    unittest.main()
