from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_navigation_preferences_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import User
from app.services.auth_service import generate_token


class NavigationPreferenceRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            manager = User(nome="Gestor Navegação", login="gestor_nav", tipo="gestor", ativo=True)
            manager.set_password("teste123")
            driver = User(nome="Motorista Navegação", login="motorista_nav", tipo="motorista", ativo=True)
            driver.set_password("teste123")
            db.session.add_all([manager, driver])
            db.session.commit()
            cls.manager_headers = {"Authorization": f"Bearer {generate_token(manager)}"}
            cls.driver_headers = {"Authorization": f"Bearer {generate_token(driver)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_favorite_and_recent_are_scoped_to_allowed_pages(self):
        access = self.client.post("/navegacao/paginas/maintenance/acessar", headers=self.manager_headers)
        self.assertEqual(access.status_code, 200, access.get_json())
        favorite = self.client.put("/navegacao/paginas/maintenance/favorito", headers=self.manager_headers)
        self.assertEqual(favorite.status_code, 200, favorite.get_json())
        preferences = self.client.get("/navegacao/preferencias", headers=self.manager_headers)
        self.assertEqual(preferences.status_code, 200, preferences.get_json())
        self.assertEqual(preferences.get_json()["data"]["favorites"][0]["page_key"], "maintenance")
        self.assertEqual(preferences.get_json()["data"]["recent"][0]["page_key"], "maintenance")

        denied = self.client.post("/navegacao/paginas/users/acessar", headers=self.driver_headers)
        self.assertEqual(denied.status_code, 403, denied.get_json())


if __name__ == "__main__":
    unittest.main()
