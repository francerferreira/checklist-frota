from __future__ import annotations

import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_vehicle_routes_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import User, Vehicle
from app.services.auth_service import generate_token


class VehicleRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            assert admin is not None
            cls.headers = {"Authorization": f"Bearer {generate_token(admin)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        with self.app.app_context():
            Vehicle.query.delete()
            db.session.commit()

    def _create_vehicle(self, **overrides) -> Vehicle:
        payload = {
            "frota": "BRIGADA 02",
            "tipo": "carreta",
            "placa": "BTS-5849",
            "ano": "S/INF",
            "modelo": "FACCHINI",
            "chassi": "9ARF14030SS36404",
            "configuracao": "",
            "atividade": "BRIGADA",
            "status": "ON",
            "local": "",
            "descricao": "",
            "ativo": True,
        }
        payload.update(overrides)
        vehicle = Vehicle(**payload)
        db.session.add(vehicle)
        db.session.commit()
        return vehicle

    def test_update_vehicle_allows_same_frota_with_matching_configuracao(self):
        suffix = uuid.uuid4().hex[:6].upper()
        with self.app.app_context():
            vehicle = self._create_vehicle(
                frota=f"BRIGADA {suffix}",
                placa=f"BTS-{suffix}",
            )
            vehicle_id = vehicle.id
            vehicle_frota = vehicle.frota

        response = self.client.put(
            f"/veiculos/{vehicle_id}",
            json={
                "frota": vehicle_frota,
                "tipo": "carreta",
                "placa": f"BTS-{suffix}",
                "ano": "S/INF",
                "modelo": "FACCHINI",
                "chassi": "9ARF14030SS36404",
                "configuracao": vehicle_frota,
                "atividade": "BRIGADA",
                "status": "ON",
                "local": "",
                "descricao": "",
                "ativo": True,
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json() or {}
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload["data"]["configuracao"], vehicle_frota)

    def test_update_vehicle_rejects_duplicate_frota_from_other_record(self):
        suffix = uuid.uuid4().hex[:6].upper()
        with self.app.app_context():
            existing = self._create_vehicle(
                frota=f"BRIGADA-A-{suffix}",
                placa=f"AAA-{suffix}",
            )
            target = self._create_vehicle(
                frota=f"BRIGADA-B-{suffix}",
                placa=f"BBB-{suffix}",
            )
            existing_id = existing.id
            target_id = target.id

        response = self.client.put(
            f"/veiculos/{target_id}",
            json={
                "frota": f"BRIGADA-A-{suffix}",
                "tipo": "carreta",
                "placa": f"BBB-{suffix}",
                "modelo": "FACCHINI",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 409, response.get_json())
        payload = response.get_json() or {}
        self.assertFalse(payload.get("success", True))
        self.assertEqual(
            payload.get("error"),
            f"A frota 'BRIGADA-A-{suffix}' ja esta cadastrada em outro equipamento.",
        )

        with self.app.app_context():
            refreshed_target = db.session.get(Vehicle, target_id)
            refreshed_existing = db.session.get(Vehicle, existing_id)
            self.assertIsNotNone(refreshed_target)
            self.assertIsNotNone(refreshed_existing)
            self.assertEqual(refreshed_target.frota, f"BRIGADA-B-{suffix}")
            self.assertEqual(refreshed_existing.frota, f"BRIGADA-A-{suffix}")


if __name__ == "__main__":
    unittest.main()
