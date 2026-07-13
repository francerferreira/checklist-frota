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
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_emergency_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import EquipmentFamily, EquipmentProfile, User, Vehicle
from app.services.auth_service import generate_token


class EmergencyWorkOrderRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").one()
            mechanic = User(nome="Mecanico Fase 4", login="mecanico_f4", tipo="mecanico", ativo=True)
            mechanic.set_password("teste123")
            db.session.add(mechanic)
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG FASE 4", tipo="rtg", ativo=True)
            db.session.add(vehicle)
            db.session.flush()
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id))
            db.session.commit()
            cls.vehicle_id = vehicle.id
            cls.mechanic_id = mechanic.id
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.mechanic_headers = {"Authorization": f"Bearer {generate_token(mechanic)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_complete_emergency_flow_restores_availability(self):
        opened = self.client.post(
            "/emergenciais",
            json={
                "vehicle_id": self.vehicle_id,
                "severity": "CRITICA",
                "equipment_stopped": True,
                "title": "Falha hidraulica",
                "description": "Equipamento perdeu pressao durante a operacao.",
                "evidence_path": "/uploads/emergencia-antes.jpg",
            },
            headers=self.mechanic_headers,
        )
        self.assertEqual(opened.status_code, 201, opened.get_json())
        emergency = opened.get_json()["data"]
        self.assertTrue(emergency["event_number"].startswith("EMG-"))
        self.assertEqual(emergency["vehicle"]["operational_state"]["operational_status"], "MANUTENCAO")

        converted = self.client.post(
            f"/emergenciais/{emergency['id']}/converter-os",
            json={"assigned_mechanic_user_id": self.mechanic_id},
            headers=self.admin_headers,
        )
        self.assertEqual(converted.status_code, 201, converted.get_json())
        emergency = converted.get_json()["data"]
        work_order_id = emergency["work_order_id"]
        self.assertEqual(emergency["work_order"]["status"], "PROGRAMADA")
        self.assertEqual(emergency["work_order"]["schedule_title"].split()[0], "Emergencial")

        started = self.client.put(
            f"/ordens-servico/{work_order_id}/iniciar",
            json={"diagnosis": "Mangueira principal rompida", "before_evidence_path": "/uploads/os-antes.jpg"},
            headers=self.mechanic_headers,
        )
        self.assertEqual(started.status_code, 200, started.get_json())
        completed = self.client.put(
            f"/ordens-servico/{work_order_id}/concluir-reparo",
            json={"service_performed": "Mangueira substituida e circuito pressurizado", "after_evidence_path": "/uploads/os-depois.jpg"},
            headers=self.mechanic_headers,
        )
        self.assertEqual(completed.status_code, 200, completed.get_json())

        rejected = self.client.put(
            f"/ordens-servico/{work_order_id}/teste",
            json={"test_result": "REPROVADO", "test_notes": "Persistiu vazamento"},
            headers=self.mechanic_headers,
        )
        self.assertEqual(rejected.status_code, 200, rejected.get_json())
        blocked = self.client.put(f"/ordens-servico/{work_order_id}/liberar", json={}, headers=self.mechanic_headers)
        self.assertEqual(blocked.status_code, 400, blocked.get_json())

        approved = self.client.put(
            f"/ordens-servico/{work_order_id}/teste",
            json={"test_result": "APROVADO", "test_notes": "Teste sem vazamento", "test_evidence_path": "/uploads/teste.jpg"},
            headers=self.mechanic_headers,
        )
        self.assertEqual(approved.status_code, 200, approved.get_json())
        released = self.client.put(f"/ordens-servico/{work_order_id}/liberar", json={}, headers=self.mechanic_headers)
        self.assertEqual(released.status_code, 200, released.get_json())
        self.assertEqual(released.get_json()["data"]["status"], "CONCLUIDA")

        detail = self.client.get(f"/emergenciais/{emergency['id']}", headers=self.admin_headers).get_json()["data"]
        self.assertEqual(detail["status"], "ENCERRADA")
        self.assertEqual(detail["execution"]["release_status"], "LIBERADO")
        self.assertEqual(detail["vehicle"]["operational_state"]["operational_status"], "DISPONIVEL")


if __name__ == "__main__":
    unittest.main()
