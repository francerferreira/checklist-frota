from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_availability_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import (
    EquipmentFamily, EquipmentOperationalState, EquipmentProfile,
    EquipmentStatusEvent, HourmeterReading, User, Vehicle,
)
from app.services.auth_service import generate_token
from app.utils.timezone import now_manaus_naive


class AvailabilityRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            cls.user_id = admin.id
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
            HourmeterReading.query.delete()
            EquipmentStatusEvent.query.delete()
            EquipmentOperationalState.query.delete()
            EquipmentProfile.query.delete()
            Vehicle.query.delete()
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG TESTE", tipo="rtg", ativo=True)
            db.session.add(vehicle)
            db.session.flush()
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id))
            db.session.add(EquipmentOperationalState(vehicle_id=vehicle.id))
            db.session.commit()
            self.vehicle_id = vehicle.id

    def test_initial_state_is_unreported_and_reason_is_required(self):
        response = self.client.get("/disponibilidade/visao", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        row = response.get_json()["data"]["rows"][0]
        self.assertEqual(row["vehicle"]["operational_state"]["operational_status"], "SEM_APONTAMENTO")
        self.assertIsNone(row["availability_percentage"])

        response = self.client.put(
            f"/equipamentos/{self.vehicle_id}/status-operacional",
            json={"status": "INDISPONIVEL"}, headers=self.headers,
        )
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertIn("motivo", response.get_json()["error"].lower())

    def test_status_transition_closes_previous_event(self):
        first_at = now_manaus_naive() - timedelta(hours=2)
        second_at = now_manaus_naive() - timedelta(hours=1)
        first = self.client.put(
            f"/equipamentos/{self.vehicle_id}/status-operacional",
            json={"status": "DISPONIVEL", "started_at": first_at.isoformat()}, headers=self.headers,
        )
        second = self.client.put(
            f"/equipamentos/{self.vehicle_id}/status-operacional",
            json={"status": "MANUTENCAO", "reason": "Teste", "started_at": second_at.isoformat()},
            headers=self.headers,
        )
        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertEqual(second.status_code, 200, second.get_json())
        history = self.client.get(
            f"/equipamentos/{self.vehicle_id}/status-historico", headers=self.headers,
        ).get_json()["data"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["status"], "MANUTENCAO")
        self.assertEqual(history[1]["ended_at"], second_at.isoformat())

    def test_availability_uses_only_periods_with_status_events(self):
        # Meio-dia do dia anterior evita virar a data e não depende do horário atual de Manaus.
        now = (now_manaus_naive() - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        with self.app.app_context():
            db.session.add_all([
                EquipmentStatusEvent(
                    vehicle_id=self.vehicle_id, status="DISPONIVEL", source="MANUAL",
                    started_at=now - timedelta(hours=3), ended_at=now - timedelta(hours=1),
                    created_by_user_id=self.user_id,
                ),
                EquipmentStatusEvent(
                    vehicle_id=self.vehicle_id, status="INDISPONIVEL", reason="Teste", source="MANUAL",
                    started_at=now - timedelta(hours=1), ended_at=now,
                    created_by_user_id=self.user_id,
                ),
            ])
            db.session.commit()
        response = self.client.get(
            f"/disponibilidade/visao?data_inicial={now.date()}&data_final={now.date()}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["data"]["rows"][0]["availability_percentage"], 66.67)

    def test_hourmeter_is_append_only_and_monotonic(self):
        first_at = now_manaus_naive() - timedelta(hours=1)
        first = self.client.post(
            f"/equipamentos/{self.vehicle_id}/horimetros",
            json={"reading": 1250.5, "recorded_at": first_at.isoformat()}, headers=self.headers,
        )
        self.assertEqual(first.status_code, 201, first.get_json())
        invalid = self.client.post(
            f"/equipamentos/{self.vehicle_id}/horimetros",
            json={"reading": 1200}, headers=self.headers,
        )
        self.assertEqual(invalid.status_code, 400, invalid.get_json())
        valid = self.client.post(
            f"/equipamentos/{self.vehicle_id}/horimetros",
            json={"reading": 1251.75}, headers=self.headers,
        )
        self.assertEqual(valid.status_code, 201, valid.get_json())
        history = self.client.get(
            f"/equipamentos/{self.vehicle_id}/horimetros", headers=self.headers,
        ).get_json()["data"]
        self.assertEqual([item["reading"] for item in history], [1251.75, 1250.5])


if __name__ == "__main__":
    unittest.main()
