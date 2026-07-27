from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

from PySide6.QtTest import QTest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from access import allowed_pages_for_role, user_can
from api_client import APIClient
from components.loading_overlay import LoadingOverlay
from components.table_skeleton import TableSkeletonOverlay
from ui.main_window import MainWindow
from ui.users_page import UsersPage


class FakeAPIClient:
    def __init__(self):
        self.base_url = "http://127.0.0.1:5000"
        self.user = {"login": "admin"}
        self.calls = {
            "dashboard": 0,
            "operations_center": 0,
            "nc": 0,
            "productivity": 0,
            "equipment": 0,
            "materials": 0,
            "activities": 0,
            "availability": 0,
            "inspection_templates": 0,
            "pcm": 0,
            "resources": 0,
            "purchases": 0,
            "supply_library": 0,
            "reports_macro": 0,
            "reports_micro": 0,
            "reports_item": 0,
            "checklist_history": 0,
            "users": 0,
            "images": 0,
        }
        self.navigation_preferences = {"favorites": [], "recent": []}

    def get_dashboard(self):
        self.calls["dashboard"] += 1
        return {
            "total_nc": 3,
            "nc_abertas": 1,
            "veiculos_com_falha": 2,
            "itens_criticos": [
                {"item_nome": "Farol", "total_nc": 2, "abertas": 1, "resolvidas": 1}
            ],
        }

    def get_non_conformities(self, **kwargs):
        self.calls["nc"] += 1
        return []

    def get_mechanic_non_conformities(self, status=None):
        return []

    def get_productivity_report(self):
        self.calls["productivity"] += 1
        return {"resumo": {}, "usuarios": []}

    def get_equipment(self, tipo=None, ativos=None):
        self.calls["equipment"] += 1
        return []

    def get_activities(self, tipo=None, status=None, item_name=None, mechanic_id=None):
        self.calls["activities"] += 1
        return []

    def get_availability_overview(self, **kwargs):
        self.calls["availability"] += 1
        return {
            "summary": {
                "total": 1,
                "status_counts": {"SEM_APONTAMENTO": 1},
                "average_availability_percentage": None,
                "measured_equipment": 0,
            },
            "rows": [],
        }

    def get_critical_equipment(self):
        self.calls["operations_center"] += 1
        return {"items": []}

    def get_equipment_structure(self):
        return {"families": [{"id": 1, "code": "rtg", "name": "RTG"}], "locations": []}

    def get_inspection_templates(self, **kwargs):
        self.calls["inspection_templates"] += 1
        return []

    def get_pcm_agenda(self, **kwargs):
        self.calls["pcm"] += 1
        return {"preventive_plans": [], "summary": {"vencendo_ou_vencidos": 0}}

    def get_pcm_backlog(self):
        return []

    def get_pcm_programming(self, **kwargs):
        return {"summary": {}, "days": [], "recommended_windows": []}

    def get_maintenance_resources(self):
        self.calls["resources"] += 1
        return []

    def get_suppliers(self):
        return []

    def get_purchase_requests(self):
        self.calls["purchases"] += 1
        return []

    def get_navigation_preferences(self):
        return self.navigation_preferences

    def toggle_navigation_favorite(self, page_key):
        favorites = self.navigation_preferences["favorites"]
        existing = next((row for row in favorites if row.get("page_key") == page_key), None)
        if existing:
            favorites.remove(existing)
            return {"page_key": page_key, "is_favorite": False}
        row = {"page_key": page_key, "is_favorite": True}
        favorites.append(row)
        return row

    def register_navigation_access(self, page_key):
        recent = [row for row in self.navigation_preferences["recent"] if row.get("page_key") != page_key]
        recent.insert(0, {"page_key": page_key})
        self.navigation_preferences["recent"] = recent[:6]
        return {"page_key": page_key}

    def get_warehouses(self):
        self.calls["supply_library"] += 1
        return []

    def get_warehouse_stocks(self):
        return []

    def get_warehouse_reservations(self):
        return []

    def get_technical_documents(self, **kwargs):
        return []

    def get_technical_inspection_executions(self, vehicle_id=None):
        return []

    def get_materials(self, tipo=None, search=None, ativos="true", baixo_estoque=None):
        self.calls["materials"] += 1
        return []

    def get_material_movements(self, material_id):
        return []

    def create_material(self, payload):
        return {"id": 1, **payload}

    def update_material(self, material_id, payload):
        return {"id": material_id, **payload}

    def delete_material(self, material_id):
        return {"status": "ok"}

    def adjust_material_stock(self, material_id, payload):
        return {"id": material_id, "quantidade_estoque": 0}

    def get_activity(self, activity_id):
        return {
            "id": activity_id,
            "titulo": "Troca em massa - Lanterna",
            "item_nome": "Lanterna",
            "tipo_equipamento": "cavalo",
            "status": "ABERTA",
            "created_at": "2026-04-11T18:00:00",
            "finalized_at": None,
            "resumo": {"total": 1, "instalados": 0, "nao_instalados": 0, "pendentes": 1},
            "itens": [],
        }

    def create_activity(self, payload):
        return {"id": 1, **payload}

    def update_activity_item(self, activity_id, item_id, payload):
        return self.get_activity(activity_id)

    def get_macro_report(self):
        self.calls["reports_macro"] += 1
        return []

    def get_micro_report(self):
        self.calls["reports_micro"] += 1
        return []

    def get_item_report(self, item_name=None, **_kwargs):
        self.calls["reports_item"] += 1
        return []

    def get_checklist_history_matrix(self, tipo=None, data_inicio=None, data_fim=None):
        self.calls["checklist_history"] += 1
        return {"columns": [], "rows": [], "periodo": {"inicio": data_inicio, "fim": data_fim}}

    def get_checklist_detail(self, checklist_id):
        return {"id": checklist_id, "vehicle": {}, "user": {}, "itens": []}

    def get_users(self):
        self.calls["users"] += 1
        return [
            {"id": 1, "nome": "Administrador", "login": "admin", "tipo": "admin", "ativo": True}
        ]

    def get_mechanics(self):
        return [
            {"id": 4, "nome": "Mecanico", "login": "mecanico", "tipo": "mecanico", "ativo": True}
        ]

    def fetch_image(self, relative_path):
        self.calls["images"] += 1
        return None


class DesktopNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.api_client = FakeAPIClient()
        self.window = MainWindow(
            self.api_client,
            {"nome": "Administrador", "tipo": "admin", "login": "admin"},
        )
        QTest.qWait(30)
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_switch_page_refreshes_only_dirty_page(self):
        self.assertEqual(self.api_client.calls["dashboard"], 1)

        self.window.switch_page("activities")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["activities"], 1)

        self.window.switch_page("materials")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["materials"], 1)

        self.window.switch_page("availability")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["availability"], 1)

        self.window.switch_page("operations_center")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["operations_center"], 1)

        self.window.switch_page("inspection_templates")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["inspection_templates"], 1)

        self.window.switch_page("pcm")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["pcm"], 1)

        self.window.switch_page("resources")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["resources"], 1)

        self.window.switch_page("purchases")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["purchases"], 1)

        self.window.switch_page("supply_library")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["supply_library"], 1)

        self.window.switch_page("users")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["users"], 1)

        self.window.switch_page("dashboard")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["dashboard"], 1)

    def test_navigation_search_filters_modules_and_updates_context(self):
        self.window.navigation_search.setText("central")
        self.app.processEvents()

        self.assertFalse(self.window.tree_items["operations_center"].isHidden())
        self.assertTrue(self.window.tree_items["equipment"].isHidden())

        self.window.switch_page("operations_center")
        self.assertEqual(
            self.window.navigation_context_label.text(),
            "NAVEGAÇÃO › CENTRAL OPERACIONAL",
        )

        self.window.navigation_search.clear()
        self.app.processEvents()
        self.assertFalse(self.window.tree_items["equipment"].isHidden())

    def test_web_panel_actions_reuse_the_active_desktop_api(self):
        with unittest.mock.patch("ui.main_window.QDesktopServices.openUrl", return_value=True) as open_url:
            self.window.open_web_mobile()
            web_mobile_url = open_url.call_args.args[0].toString(QUrl.FullyDecoded)
            self.window.open_tv_dashboard()
            tv_dashboard_url = open_url.call_args.args[0].toString(QUrl.FullyDecoded)

        self.assertEqual(web_mobile_url, "http://127.0.0.1:5500/?api=http%3A%2F%2F127.0.0.1%3A5000")
        self.assertEqual(tv_dashboard_url, "http://127.0.0.1:5500/dashboard-manutencao/tv/?api=http%3A%2F%2F127.0.0.1%3A5000")
        self.assertTrue(any(action.text() == "Painéis Web" for action in self.window.menuBar().actions()))

    def test_dashboard_has_visible_web_shortcuts(self):
        self.assertEqual(self.window.dashboard_page.web_mobile_button.objectName(), "open-web-mobile-button")
        self.assertEqual(self.window.dashboard_page.tv_dashboard_button.objectName(), "open-tv-dashboard-button")
        with unittest.mock.patch("ui.main_window.QDesktopServices.openUrl", return_value=True) as open_url:
            self.window.dashboard_page.web_mobile_button.click()
            self.window.dashboard_page.tv_dashboard_button.click()

        self.assertEqual(open_url.call_count, 2)

    def test_data_change_from_users_marks_other_pages_dirty_without_refreshing_all(self):
        self.window.switch_page("users")
        QTest.qWait(30)
        self.app.processEvents()

        self.window.handle_data_changed("users")
        QTest.qWait(30)
        self.app.processEvents()

        self.assertEqual(self.api_client.calls["dashboard"], 1)
        self.assertEqual(self.api_client.calls["nc"], 0)
        self.assertEqual(self.api_client.calls["equipment"], 0)
        self.assertEqual(self.api_client.calls["reports_macro"], 0)
        self.assertEqual(self.api_client.calls["users"], 1)
        self.assertIn("dashboard", self.window.dirty_pages)
        self.assertIn("productivity", self.window.dirty_pages)
        self.assertIn("reports", self.window.dirty_pages)
        self.assertIn("equipment", self.window.dirty_pages)
        self.assertIn("materials", self.window.dirty_pages)
        self.assertIn("activities", self.window.dirty_pages)

    def test_data_change_refreshes_only_visible_page_when_source_is_different(self):
        self.assertEqual(self.api_client.calls["dashboard"], 1)

        self.window.handle_data_changed("users")
        QTest.qWait(30)
        self.app.processEvents()

        self.assertEqual(self.api_client.calls["dashboard"], 2)
        self.assertEqual(self.api_client.calls["users"], 0)
        self.assertEqual(self.api_client.calls["reports_macro"], 0)

    def test_role_access_hides_pages_from_gestor_and_motorista(self):
        gestor_window = MainWindow(
            self.api_client,
            {"nome": "Gestor", "tipo": "gestor", "login": "gestor"},
        )
        motorista_window = MainWindow(
            self.api_client,
            {"nome": "Motorista", "tipo": "motorista", "login": "motorista"},
        )
        try:
            self.assertNotIn("users", gestor_window.page_map)
            self.assertNotIn("cloud_backup", gestor_window.page_map)
            self.assertNotIn("audit_logs", gestor_window.page_map)
            self.assertIn("maintenance", gestor_window.page_map)
            self.assertIn("operations_center", gestor_window.page_map)
            self.assertIn("availability", gestor_window.page_map)
            self.assertIn("inspection_templates", gestor_window.page_map)
            self.assertIn("pcm", gestor_window.page_map)
            self.assertIn("resources", gestor_window.page_map)
            self.assertIn("purchases", gestor_window.page_map)
            self.assertIn("supply_library", gestor_window.page_map)
            self.assertIn("hr_management", gestor_window.page_map)
            self.assertIn("vacations", gestor_window.page_map)
            self.assertIn("rtg_module", gestor_window.page_map)
            self.assertIn("lbs_module", gestor_window.page_map)
            self.assertIn("rtg_downtime", gestor_window.page_map)
            self.assertIn("lbs_downtime", gestor_window.page_map)

            self.assertEqual(set(motorista_window.page_map.keys()), {"dashboard"})
        finally:
            gestor_window.close()
            motorista_window.close()
            self.app.processEvents()

    def test_central_access_map_controls_pages_and_actions(self):
        self.assertEqual(allowed_pages_for_role("motorista"), {"dashboard"})
        self.assertNotIn("users", allowed_pages_for_role("gestor"))
        self.assertIn("vacations", allowed_pages_for_role("gestor"))
        self.assertIn("rtg_module", allowed_pages_for_role("admin"))
        self.assertIn("lbs_module", allowed_pages_for_role("gestor"))
        self.assertIn("rtg_downtime", allowed_pages_for_role("admin"))
        self.assertIn("lbs_downtime", allowed_pages_for_role("gestor"))
        self.assertTrue(user_can({"tipo": "admin"}, "manage_users"))
        self.assertFalse(user_can({"tipo": "gestor"}, "manage_users"))
        self.assertTrue(user_can({"tipo": "gestor"}, "manage_activity_materials"))
        self.assertFalse(user_can({"tipo": "motorista"}, "view_wash_values"))

    def test_family_modules_are_separate_navigation_shells(self):
        self.assertIn("rtg_module", self.window.page_map)
        self.assertIn("lbs_module", self.window.page_map)
        self.assertEqual(self.window.page_titles["rtg_module"], "Gest\u00e3o RTG")
        self.assertEqual(self.window.page_titles["lbs_module"], "Gest\u00e3o LBS")

        self.window.switch_page("rtg_module")
        self.assertEqual(self.window._navigation_section("rtg_module"), "GEST\u00c3O RTG")
        self.assertIn("GEST\u00c3O RTG", self.window.rtg_module_page.findChildren(QLabel)[0].text())

        self.window.switch_page("lbs_module")
        self.assertEqual(self.window._navigation_section("lbs_module"), "GEST\u00c3O LBS")
        self.assertIn("GEST\u00c3O LBS", self.window.lbs_module_page.findChildren(QLabel)[0].text())

        self.window.switch_page("rtg_downtime")
        self.assertEqual(self.window.page_titles["rtg_downtime"], "Controle de Paradas RTG")
        self.assertEqual(self.window._navigation_section("rtg_downtime"), "GEST\u00c3O RTG")
        self.assertEqual(self.window.rtg_downtime_page.table.rowCount(), 0)

        self.window.switch_page("lbs_downtime")
        self.assertEqual(self.window.page_titles["lbs_downtime"], "Controle de Paradas LBS")
        self.assertEqual(self.window._navigation_section("lbs_downtime"), "GEST\u00c3O LBS")
        self.assertEqual(self.window.lbs_downtime_page.table.rowCount(), 0)

    def test_users_page_hides_admin_buttons_for_gestor(self):
        gestor_page = UsersPage(
            self.api_client,
            {"nome": "Gestor", "tipo": "gestor", "login": "gestor"},
        )
        try:
            self.assertFalse(gestor_page.add_button.isVisible())
            self.assertFalse(gestor_page.edit_button.isVisible())
            self.assertFalse(gestor_page.delete_button.isVisible())
            self.assertIn("Somente o administrador", gestor_page.info_label.text())
        finally:
            gestor_page.close()
            self.app.processEvents()

    def test_table_skeleton_hides_immediately_after_loading(self):
        host = QFrame()
        host.resize(420, 260)
        host.show()
        skeleton = TableSkeletonOverlay(host, rows=4)
        try:
            skeleton.show_skeleton("Carregando teste")
            QTest.qWait(120)
            self.app.processEvents()
            self.assertTrue(skeleton.isVisible())

            skeleton.hide_skeleton()
            QTest.qWait(30)
            self.app.processEvents()
            self.assertFalse(skeleton.isVisible())
        finally:
            host.close()
            self.app.processEvents()

    def test_loading_overlay_hides_immediately_after_loading(self):
        host = QFrame()
        host.resize(420, 260)
        host.show()
        overlay = LoadingOverlay(host)
        try:
            overlay.show_loading("Carregando teste")
            QTest.qWait(120)
            self.app.processEvents()
            self.assertTrue(overlay.isVisible())

            overlay.hide_loading()
            QTest.qWait(30)
            self.app.processEvents()
            self.assertFalse(overlay.isVisible())
        finally:
            host.close()
            self.app.processEvents()


class APIClientCacheTests(unittest.TestCase):
    def test_fetch_image_uses_cache_for_same_path(self):
        client = APIClient("http://127.0.0.1:5000")
        response = Mock()
        response.ok = True
        response.content = b"image-bytes"
        client.session.get = Mock(return_value=response)

        first = client.fetch_image("/uploads/teste.png")
        second = client.fetch_image("/uploads/teste.png")

        self.assertEqual(first, b"image-bytes")
        self.assertEqual(second, b"image-bytes")
        self.assertEqual(client.session.get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
