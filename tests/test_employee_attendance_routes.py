from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_employee_attendance_routes_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import Employee, EmployeeAttendanceRecord, EmployeeVacation, User
from app.services.auth_service import generate_token


class EmployeeAttendanceRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            cls.manager = User(nome="Gestor Frequencia", login="gestor-frequencia", tipo="gestor", ativo=True)
            cls.manager.set_password("SenhaSegura123!")
            cls.driver = User(nome="Motorista Frequencia", login="motorista-frequencia", tipo="motorista", ativo=True)
            cls.driver.set_password("SenhaSegura123!")
            db.session.add_all([cls.manager, cls.driver])
            db.session.flush()
            cls.employee = Employee(
                registration="RH-FREQ-001",
                full_name="Colaborador Frequencia",
                function_name="Mecânico",
                team_name="Equipe A",
                shift_name="1º turno",
                status="ATIVO",
                user_id=cls.driver.id,
            )
            db.session.add(cls.employee)
            db.session.commit()
            cls.employee_id = cls.employee.id
            cls.manager_headers = {"Authorization": f"Bearer {generate_token(cls.manager)}"}
            cls.driver_headers = {"Authorization": f"Bearer {generate_token(cls.driver)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        for path in (DB_PATH, Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm")):
            if path.exists():
                path.unlink()

    def test_delay_is_calculated_and_correction_requires_reason(self):
        created = self.client.post(
            "/rh/frequencia",
            headers=self.manager_headers,
            json={
                "employee_id": self.employee_id,
                "occurrence_date": "2026-07-24",
                "occurrence_type": "ATRASO",
                "scheduled_time": "07:00",
                "arrival_time": "07:35",
                "reason": "Transporte",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        record = created.get_json()["data"][0]
        self.assertEqual(record["delay_minutes"], 35)

        missing_reason = self.client.put(
            f"/rh/frequencia/{record['id']}",
            headers=self.manager_headers,
            json={
                "employee_id": self.employee_id,
                "occurrence_date": "2026-07-24",
                "occurrence_type": "PRESENTE",
            },
        )
        self.assertEqual(missing_reason.status_code, 400, missing_reason.get_json())

        corrected = self.client.put(
            f"/rh/frequencia/{record['id']}",
            headers=self.manager_headers,
            json={
                "employee_id": self.employee_id,
                "occurrence_date": "2026-07-24",
                "occurrence_type": "PRESENTE",
                "change_reason": "Chegada corrigida após conferência",
            },
        )
        self.assertEqual(corrected.status_code, 200, corrected.get_json())
        self.assertEqual(corrected.get_json()["data"]["occurrence_type"], "PRESENTE")

    def test_medical_certificate_period_and_cancellation_keep_records(self):
        created = self.client.post(
            "/rh/frequencia",
            headers=self.manager_headers,
            json={
                "employee_id": self.employee_id,
                "occurrence_date": "2026-07-25",
                "end_date": "2026-07-26",
                "occurrence_type": "ATESTADO",
                "is_justified": True,
                "document_path": "/uploads/atestado-rh.pdf",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        records = created.get_json()["data"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["occurrence_type"], "ATESTADO")

        cancelled = self.client.post(
            f"/rh/frequencia/{records[0]['id']}/cancelar",
            headers=self.manager_headers,
            json={"reason": "Documento substituído"},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.get_json())
        self.assertEqual(cancelled.get_json()["data"]["record_status"], "CANCELADO")
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(EmployeeAttendanceRecord, records[0]["id"]))

    def test_profile_without_hr_management_access_is_denied(self):
        response = self.client.get("/rh/frequencia", headers=self.driver_headers)
        self.assertEqual(response.status_code, 403, response.get_json())

    def test_mobile_absenteeism_reuses_daily_attendance_and_vacation(self):
        reference_date = "2026-08-03"
        loaded = self.client.get(f"/rh/absenteismo-mobile?data={reference_date}", headers=self.manager_headers)
        self.assertEqual(loaded.status_code, 200, loaded.get_json())
        self.assertEqual(loaded.get_json()["data"]["rows"][0]["occurrence_type"], "PRESENTE")
        saved = self.client.post("/rh/absenteismo-mobile", headers=self.manager_headers, json={"date": reference_date, "entries": [{"employee_id": self.employee_id, "occurrence_type": "FALTA", "notes": "Sem aviso"}]})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        with self.app.app_context():
            db.session.add(EmployeeVacation(employee_id=self.employee_id, starts_on=date(2026, 8, 4), ends_on=date(2026, 8, 5), status="APROVADA", created_by_user_id=self.manager.id))
            db.session.commit()
        vacation = self.client.get("/rh/absenteismo-mobile?data=2026-08-04", headers=self.manager_headers)
        row = vacation.get_json()["data"]["rows"][0]
        self.assertEqual(row["occurrence_type"], "FERIAS")
        self.assertTrue(row["automatic_vacation"])


if __name__ == "__main__":
    unittest.main()
