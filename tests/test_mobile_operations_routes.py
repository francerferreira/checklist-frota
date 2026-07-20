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

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_mobile_operations_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import EquipmentFamily, EquipmentProfile, HourmeterReading, MobileSyncOperation, User, Vehicle
from app.services.auth_service import generate_token


class MobileOperationsRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            if not admin:
                admin = User(nome="Administrador Teste", login="admin", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
                db.session.flush()
            mechanic = User(nome="Mecanico Mobile", login="mecanico_mobile", tipo="mecanico", ativo=True)
            mechanic.set_password("teste123")
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG MOBILE", tipo="rtg", ativo=True)
            db.session.add_all([mechanic, vehicle])
            db.session.flush()
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id))
            db.session.commit()
            cls.vehicle_id = vehicle.id
            cls.access_code = vehicle.to_dict()["mobile_access_code"]
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.mechanic_headers = {"Authorization": f"Bearer {generate_token(mechanic)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_asset_code_opens_the_active_equipment(self):
        response = self.client.get(f"/operacao-mobile/ativos/{self.access_code}", headers=self.mechanic_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()["data"]
        self.assertEqual(data["access_code"], self.access_code)
        self.assertEqual(data["vehicle"]["id"], self.vehicle_id)

    def test_hourmeter_sync_is_idempotent_and_conflicts_are_retained(self):
        operation_id = "mobile-hourmeter-0001"
        payload = {
            "operation_id": operation_id,
            "operation_type": "HORIMETRO",
            "payload": {"vehicle_id": self.vehicle_id, "reading": 1200.5, "notes": "Leitura offline"},
        }
        first = self.client.post("/operacao-mobile/sincronizar", json=payload, headers=self.mechanic_headers)
        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertFalse(first.get_json()["data"]["replayed"])
        repeated = self.client.post("/operacao-mobile/sincronizar", json=payload, headers=self.mechanic_headers)
        self.assertEqual(repeated.status_code, 200, repeated.get_json())
        self.assertTrue(repeated.get_json()["data"]["replayed"])

        conflict_payload = {
            "operation_id": "mobile-hourmeter-0002",
            "operation_type": "HORIMETRO",
            "payload": {"vehicle_id": self.vehicle_id, "reading": 1100},
        }
        conflict = self.client.post("/operacao-mobile/sincronizar", json=conflict_payload, headers=self.mechanic_headers)
        self.assertEqual(conflict.status_code, 409, conflict.get_json())
        repeated_conflict = self.client.post("/operacao-mobile/sincronizar", json=conflict_payload, headers=self.mechanic_headers)
        self.assertEqual(repeated_conflict.status_code, 409, repeated_conflict.get_json())
        with self.app.app_context():
            self.assertEqual(HourmeterReading.query.filter_by(vehicle_id=self.vehicle_id).count(), 1)
            self.assertEqual(MobileSyncOperation.query.filter_by(status="CONFLITO").count(), 1)

    def test_emergency_sync_replay_does_not_create_a_second_event(self):
        payload = {
            "operation_id": "mobile-emergency-0001",
            "operation_type": "EMERGENCIA",
            "payload": {
                "vehicle_id": self.vehicle_id,
                "severity": "ALTA",
                "equipment_stopped": True,
                "title": "Falha de campo",
                "description": "Registro feito no aparelho sem sinal.",
            },
        }
        first = self.client.post("/operacao-mobile/sincronizar", json=payload, headers=self.mechanic_headers)
        repeated = self.client.post("/operacao-mobile/sincronizar", json=payload, headers=self.mechanic_headers)
        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertEqual(repeated.status_code, 200, repeated.get_json())
        self.assertTrue(repeated.get_json()["data"]["replayed"])
        self.assertEqual(first.get_json()["data"]["result"]["emergency"]["event_number"], repeated.get_json()["data"]["result"]["emergency"]["event_number"])


if __name__ == "__main__":
    unittest.main()
