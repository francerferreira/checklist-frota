from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_pcm_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import EquipmentFamily, EquipmentProfile, MaintenanceScheduleItem, User, Vehicle
from app.services.auth_service import generate_token


class PCMRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists(): DB_PATH.unlink()
        cls.app = create_app(); cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            if not admin:
                admin = User(nome="Administrador PCM", login="admin", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
            mechanic = User(nome="Mecanico PCM", login="mecanico_pcm", tipo="mecanico", ativo=True); mechanic.set_password("teste123")
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG PCM", tipo="rtg", ativo=True)
            db.session.add_all([mechanic, vehicle]); db.session.flush()
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id)); db.session.commit()
            cls.vehicle_id, cls.mechanic_id = vehicle.id, mechanic.id
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.mechanic_headers = {"Authorization": f"Bearer {generate_token(mechanic)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context(): db.session.remove(); db.engine.dispose()
        if DB_PATH.exists(): DB_PATH.unlink()

    def test_calendar_plan_generates_single_os_and_advances_after_execution(self):
        created = self.client.post("/pcm/planos-preventivos", json={
            "vehicle_id": self.vehicle_id, "title": "Lubrificação mensal", "trigger_type": "CALENDARIO",
            "interval_days": 30, "next_due_date": date.today().isoformat(), "priority": "ALTA",
            "assigned_mechanic_user_id": self.mechanic_id,
        }, headers=self.admin_headers)
        self.assertEqual(created.status_code, 201, created.get_json())
        plan = created.get_json()["data"]
        self.assertTrue(plan["code"].startswith("PP-"))
        programming = self.client.get(
            f"/pcm/programacao?data_inicial={date.today().isoformat()}&data_final={(date.today() + timedelta(days=3)).isoformat()}&capacidade_minutos=60",
            headers=self.admin_headers,
        )
        self.assertEqual(programming.status_code, 200, programming.get_json())
        projection = programming.get_json()["data"]
        self.assertEqual(len(projection["days"]), 4)
        recommendation = next(row for row in projection["recommended_windows"] if row["plan_id"] == plan["id"])
        self.assertEqual(recommendation["status"], "PROGRAMAR")
        self.assertEqual(recommendation["estimated_duration_minutes"], 60)

        generated = self.client.post("/pcm/gerar-preventivas", json={"plan_id": plan["id"]}, headers=self.admin_headers)
        self.assertEqual(generated.status_code, 200, generated.get_json())
        items = generated.get_json()["data"]
        self.assertEqual(len(items), 1)
        schedule = items[0]["schedule"]
        self.assertEqual(schedule["source_type"], "PREVENTIVA")
        self.assertEqual(schedule["ordens_servico"][0]["status"], "PROGRAMADA")

        duplicate = self.client.post("/pcm/gerar-preventivas", json={"plan_id": plan["id"]}, headers=self.admin_headers)
        self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        self.assertEqual(duplicate.get_json()["data"], [])
        item_id = schedule["itens"][0]["id"]
        done = self.client.put(f"/manutencao/itens/{item_id}", json={"status": "INSTALADO", "photo_after": "/uploads/pcm.jpg"}, headers=self.mechanic_headers)
        self.assertEqual(done.status_code, 200, done.get_json())

        plans = self.client.get("/pcm/planos-preventivos", headers=self.admin_headers).get_json()["data"]
        updated = next(row for row in plans if row["id"] == plan["id"])
        self.assertEqual(updated["next_due_date"], (date.today() + timedelta(days=30)).isoformat())
        backlog = self.client.get("/pcm/backlog", headers=self.admin_headers).get_json()["data"]
        self.assertFalse(any(row["work_order"]["schedule_id"] == schedule["id"] for row in backlog))

    def test_pcm_requires_management_role(self):
        response = self.client.get("/pcm/agenda", headers=self.mechanic_headers)
        self.assertEqual(response.status_code, 403, response.get_json())


if __name__ == "__main__":
    unittest.main()
