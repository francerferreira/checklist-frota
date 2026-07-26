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

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_employee_vacation_routes_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import Employee, User
from app.services.auth_service import generate_token


class EmployeeVacationRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User(nome="Admin RH", login="admin-ferias", tipo="admin", ativo=True)
            admin.set_password("SenhaSegura123!")
            db.session.add(admin)
            db.session.flush()
            cls.employee = Employee(
                registration="FER-001",
                full_name="Colaborador Ferias",
                function_name="Mecanico",
                team_name="MANUTENCAO",
                shift_name="1 TURNO",
                status="ATIVO",
            )
            cls.employee_two = Employee(
                registration="FER-002",
                full_name="Colaborador DSR",
                function_name="Tecnico",
                team_name="MANUTENCAO",
                shift_name="2 TURNO",
                status="ATIVO",
            )
            db.session.add_all([cls.employee, cls.employee_two])
            db.session.flush()
            cls.employee_id = cls.employee.id
            cls.employee_two_id = cls.employee_two.id
            db.session.commit()
            cls.headers = {"Authorization": f"Bearer {generate_token(admin)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        for path in (DB_PATH, Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm")):
            if path.exists():
                path.unlink()

    def test_vacation_calendar_rejects_overlapping_periods(self):
        created = self.client.post(
            "/rh/ferias",
            headers=self.headers,
            json={
                "employee_id": self.employee_id,
                "starts_on": "2026-08-10",
                "ends_on": "2026-08-19",
                "status": "PROGRAMADA",
                "notes": "Ferias programadas",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        rows = self.client.get(
            "/rh/ferias?data_inicial=2026-08-01&data_final=2026-08-31",
            headers=self.headers,
        )
        self.assertEqual(rows.status_code, 200, rows.get_json())
        self.assertEqual(len(rows.get_json()["data"]), 1)

        conflict = self.client.post(
            "/rh/ferias",
            headers=self.headers,
            json={
                "employee_id": self.employee_id,
                "starts_on": "2026-08-15",
                "ends_on": "2026-08-25",
            },
        )
        self.assertEqual(conflict.status_code, 400, conflict.get_json())
        self.assertIn("ja possui ferias", conflict.get_json()["error"])

    def test_weekly_dsr_uses_sunday_and_is_idempotent(self):
        week_start = date(2026, 7, 20)
        created = self.client.post(
            "/rh/dsr-semanal",
            headers=self.headers,
            json={"week_start": week_start.isoformat(), "employee_ids": [self.employee_two_id]},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        data = created.get_json()["data"]
        self.assertEqual(data["dsr_date"], (week_start + timedelta(days=6)).isoformat())
        self.assertEqual(len(data["created"]), 1)
        self.assertEqual(data["created"][0]["occurrence_type"], "DSR")

        repeated = self.client.post(
            "/rh/dsr-semanal",
            headers=self.headers,
            json={"week_start": week_start.isoformat(), "employee_ids": [self.employee_two_id]},
        )
        self.assertEqual(repeated.status_code, 201, repeated.get_json())
        self.assertEqual(len(repeated.get_json()["data"]["created"]), 0)
        self.assertEqual(repeated.get_json()["data"]["already_registered"], 1)


if __name__ == "__main__":
    unittest.main()
