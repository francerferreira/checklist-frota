from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_governance_controls_call_protected_maintenance_routes():
    html = (ROOT / "web_app" / "dashboard-manutencao" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web_app" / "static" / "js" / "maintenance-dashboard.js").read_text(encoding="utf-8")

    assert "dashboard-governance-panel" in html
    assert "dashboard-governance-targets-form" in html
    assert "dashboard-governance-cost-form" in html
    assert "/manutencao/governanca/metas" in script
    assert "/manutencao/os/${workOrderId}/classificacao" in script
    assert "/manutencao/os/${workOrderId}/custos" in script
