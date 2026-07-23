from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_resources_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import User
from app.services.auth_service import generate_token


class ResourceRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User(nome="Administrador Recursos", login="admin_recursos", tipo="admin", ativo=True)
            admin.set_password("teste123")
            mechanic = User(nome="Mecanico Recursos", login="mecanico_recursos", tipo="mecanico", ativo=True)
            mechanic.set_password("teste123")
            db.session.add_all([admin, mechanic])
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

    def create_resource(self, **overrides):
        payload = {
            "code": "TORQ-01",
            "name": "Torquímetro",
            "resource_type": "INSTRUMENTO",
            "calibration_required": True,
            "calibration_due_date": (date.today() + timedelta(days=30)).isoformat(),
        }
        payload.update(overrides)
        response = self.client.post("/recursos", json=payload, headers=self.admin_headers)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["data"]

    def test_reservation_blocks_overlap_and_allows_after_cancellation(self):
        resource = self.create_resource()
        starts_at = datetime(2026, 7, 24, 8, 0)
        first = self.client.post(
            f"/recursos/{resource['id']}/reservas",
            json={"starts_at": starts_at.isoformat(), "ends_at": (starts_at + timedelta(hours=2)).isoformat()},
            headers=self.admin_headers,
        )
        self.assertEqual(first.status_code, 201, first.get_json())
        reservation = first.get_json()["data"]

        conflict = self.client.post(
            f"/recursos/{resource['id']}/reservas",
            json={"starts_at": (starts_at + timedelta(hours=1)).isoformat(), "ends_at": (starts_at + timedelta(hours=3)).isoformat()},
            headers=self.admin_headers,
        )
        self.assertEqual(conflict.status_code, 400, conflict.get_json())

        cancelled = self.client.post(
            f"/recursos/reservas/{reservation['id']}/cancelar",
            json={"reason": "Reprogramação"},
            headers=self.admin_headers,
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.get_json())

        replacement = self.client.post(
            f"/recursos/{resource['id']}/reservas",
            json={"starts_at": (starts_at + timedelta(hours=1)).isoformat(), "ends_at": (starts_at + timedelta(hours=3)).isoformat()},
            headers=self.admin_headers,
        )
        self.assertEqual(replacement.status_code, 201, replacement.get_json())

    def test_expired_calibration_blocks_reservation_and_mechanic_cannot_manage(self):
        expired = self.create_resource(
            code="MED-02",
            name="Medidor de pressão",
            calibration_due_date=(date.today() - timedelta(days=1)).isoformat(),
        )
        denied = self.client.post(
            f"/recursos/{expired['id']}/reservas",
            json={"starts_at": "2026-07-24T08:00", "ends_at": "2026-07-24T09:00"},
            headers=self.admin_headers,
        )
        self.assertEqual(denied.status_code, 400, denied.get_json())

        mechanic = self.client.get("/recursos", headers=self.mechanic_headers)
        self.assertEqual(mechanic.status_code, 403, mechanic.get_json())


if __name__ == "__main__":
    unittest.main()
