from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "web_app" / "dashboard-tv" / "manutencao" / "index.html"
CSS = ROOT / "web_app" / "static" / "css" / "dashboard-tv-maintenance.css"
JS = ROOT / "web_app" / "static" / "js" / "dashboard-tv-maintenance.js"


class MaintenanceDashboardTvVisualContractTest(unittest.TestCase):
    def test_four_pages_have_operational_regions(self):
        html = HTML.read_text(encoding="utf-8")
        for region in ("operational", "offenders", "execution", "preventives", "backlog", "actions"):
            self.assertIn(f'data-shell-list="{region}"', html)
        for table in ("schedule", "materials"):
            self.assertIn(f'data-shell-table="{table}"', html)
        self.assertNotIn("Etapa 3", html)

    def test_visual_rendering_has_status_and_evidence_components(self):
        css = CSS.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        for token in ("status-chip", "metric-track", "critical-row", "preventive-row", "backlog-row", "action-row"):
            self.assertIn(token, css)
        for token in ("formatDate", "toneForStatus", "statusChip", "data_availability"):
            self.assertIn(token, js)
        self.assertIn("Sem previsao de liberacao", js)
        self.assertIn("Planos de acao ainda nao possuem cadastro proprio no banco.", js)

    def test_final_operation_contract_is_present(self):
        html = HTML.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn("footer-legend", html)
        self.assertIn("ROTAÇÃO: 40 S", html)
        self.assertIn("width: 100vw", css)
        self.assertIn("height: 100vh", css)
        self.assertIn("ÚLTIMOS DADOS VÁLIDOS", js)
        self.assertIn("FALHA AO ATUALIZAR", js)


if __name__ == "__main__":
    unittest.main()
