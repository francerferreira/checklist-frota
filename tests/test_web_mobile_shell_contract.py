from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML_PATH = PROJECT_ROOT / "web_app" / "index.html"
LEGACY_README_PATH = PROJECT_ROOT / "web_app" / "static" / "js" / "README_LEGADO.txt"


class WebMobileShellContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index_html = INDEX_HTML_PATH.read_text(encoding="utf-8")
        cls.legacy_readme = LEGACY_README_PATH.read_text(encoding="utf-8")

    def test_index_uses_canonical_frontend_bundle(self):
        self.assertIn('./static/js/app.js?v=20260501-08', self.index_html)
        self.assertIn('./static/css/styles.css?v=20260501-08', self.index_html)
        self.assertNotIn("app-20260419-", self.index_html)

    def test_frontend_uses_manaus_timezone_for_dates(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('const MANAUS_TIME_ZONE = "America/Manaus"', app_js)
        self.assertIn("window.CHECKLIST_TIME_ZONE = MANAUS_TIME_ZONE", app_js)
        self.assertIn("formatManausDateTime", app_js)

    def test_index_does_not_restore_removed_inline_fallbacks(self):
        self.assertNotIn("data-inline-fallback", self.index_html)
        self.assertNotIn("fetch(cssUrl", self.index_html)
        self.assertNotIn("stopImmediatePropagation", self.index_html)

    def test_operational_screens_and_wash_structure_remain_available(self):
        expected_fragments = [
            'id="open-checklist-history-menu"',
            'id="open-maintenance-menu"',
            'id="checklist-history-screen"',
            'class="module-section history-filter-card"',
            'id="maintenance-screen"',
            'id="wash-calendar"',
            'id="wash-day-panel"',
            'id="washes-list"',
            'id="pull-refresh-indicator"',
            'id="photo-viewer-modal"',
        ]
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.index_html)

    def test_index_removes_screen_overlines_from_operational_shell(self):
        self.assertNotIn('class="overline"', self.index_html)

    def test_legacy_readme_keeps_app_js_as_single_frontend_reference(self):
        self.assertIn("app.js", self.legacy_readme)
        self.assertIn("arquivo canonico", self.legacy_readme.lower())


if __name__ == "__main__":
    unittest.main()
