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
from PySide6.QtWidgets import QApplication

from api_client import APIClient
from ui.main_window import MainWindow


class FakeAPIClient:
    def __init__(self):
        self.user = {"login": "admin"}
        self.calls = {
            "dashboard": 0,
            "nc": 0,
            "productivity": 0,
            "equipment": 0,
            "materials": 0,
            "activities": 0,
            "reports_macro": 0,
            "reports_micro": 0,
            "reports_item": 0,
            "users": 0,
            "images": 0,
        }

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

        self.window.switch_page("users")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["users"], 1)

        self.window.switch_page("dashboard")
        QTest.qWait(30)
        self.app.processEvents()
        self.assertEqual(self.api_client.calls["dashboard"], 1)

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
