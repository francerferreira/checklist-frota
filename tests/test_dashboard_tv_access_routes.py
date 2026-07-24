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

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_dashboard_tv_access_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import DashboardTvAccessToken, User
from app.services.auth_service import generate_token


class DashboardTvAccessRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin_tv").first()
            if not admin:
                admin = User(nome="Administrador TV", login="admin_tv", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
            mechanic = User.query.filter_by(login="mecanico_tv").first()
            if not mechanic:
                mechanic = User(nome="Mecanico TV", login="mecanico_tv", tipo="mecanico", ativo=True)
                mechanic.set_password("teste123")
                db.session.add(mechanic)
            db.session.commit()
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.mechanic_headers = {"Authorization": f"Bearer {generate_token(mechanic)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def setUp(self):
        with self.app.app_context():
            DashboardTvAccessToken.query.delete()
            db.session.commit()

    def test_tv_data_is_public_even_after_legacy_access_is_revoked(self):
        created = self.client.post(
            "/dashboard-manutencao/tv/acessos",
            headers=self.admin_headers,
            json={"name": "TV Patio", "expires_in_minutes": 120},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        payload = created.get_json()["data"]
        raw_token = payload["token"]
        self.assertTrue(raw_token.startswith("tv_"))
        self.assertNotIn("token_hash", payload["access"])

        listed = self.client.get("/dashboard-manutencao/tv/acessos", headers=self.admin_headers)
        self.assertEqual(listed.status_code, 200, listed.get_json())
        self.assertEqual(len(listed.get_json()["data"]["items"]), 1)
        self.assertNotIn(raw_token, str(listed.get_json()))

        tv_data = self.client.get("/dashboard-manutencao/tv/dados")
        self.assertEqual(tv_data.status_code, 200, tv_data.get_json())
        dashboard = tv_data.get_json()["data"]
        self.assertIn("kpis", dashboard)
        self.assertNotIn("unavailability_reasons", dashboard)
        self.assertNotIn("data_availability", dashboard)

        revoked = self.client.delete(
            f"/dashboard-manutencao/tv/acessos/{payload['access']['id']}",
            headers=self.admin_headers,
        )
        self.assertEqual(revoked.status_code, 200, revoked.get_json())
        still_open = self.client.get("/dashboard-manutencao/tv/dados")
        self.assertEqual(still_open.status_code, 200, still_open.get_json())

    def test_only_management_can_issue_tv_access(self):
        denied = self.client.post(
            "/dashboard-manutencao/tv/acessos",
            headers=self.mechanic_headers,
            json={"expires_in_minutes": 120},
        )
        self.assertEqual(denied.status_code, 403, denied.get_json())
        invalid_duration = self.client.post(
            "/dashboard-manutencao/tv/acessos",
            headers=self.admin_headers,
            json={"expires_in_minutes": 14},
        )
        self.assertEqual(invalid_duration.status_code, 400, invalid_duration.get_json())

    def test_public_tv_route_is_allowed_for_configured_web_origin(self):
        response = self.client.options(
            "/dashboard-manutencao/tv/dados",
            headers={
                "Origin": "https://checklist-web-uej3.onrender.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://checklist-web-uej3.onrender.com")


if __name__ == "__main__":
    unittest.main()
