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

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_hr_management_routes_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import AuditLog, Employee, EmployeeAttendanceRecord, EmployeeDocument, EmployeeTraining, User
from app.services.auth_service import generate_token


class HRManagementRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            cls.admin = User(nome="Admin Painel", login="admin-painel-rh", tipo="admin", ativo=True)
            cls.admin.set_password("SenhaSegura123!")
            cls.manager = User(nome="Gestor Painel", login="gestor-painel-rh", tipo="gestor", ativo=True)
            cls.manager.set_password("SenhaSegura123!")
            cls.driver = User(nome="Motorista Painel", login="motorista-painel-rh", tipo="motorista", ativo=True)
            cls.driver.set_password("SenhaSegura123!")
            db.session.add_all([cls.admin, cls.manager, cls.driver])
            db.session.flush()
            active = Employee(registration="RH-PNL-001", full_name="Ativo Painel", function_name="Mecanico", team_name="Equipe A", shift_name="1 turno", status="ATIVO")
            inactive = Employee(registration="RH-PNL-002", full_name="Inativo Painel", function_name="Motorista", team_name="Equipe B", shift_name="2 turno", status="INATIVO")
            db.session.add_all([active, inactive])
            db.session.flush()
            today = date.today()
            db.session.add_all([
                EmployeeAttendanceRecord(employee_id=active.id, occurrence_date=today, occurrence_type="PRESENTE", record_status="ATIVO", created_by_user_id=cls.admin.id),
                EmployeeAttendanceRecord(employee_id=active.id, occurrence_date=today - timedelta(days=1), occurrence_type="FALTA", record_status="ATIVO", created_by_user_id=cls.admin.id),
                EmployeeDocument(employee_id=active.id, document_type="ASO", file_path="/uploads/rh/aso.pdf", expires_on=today - timedelta(days=1), is_sensitive=True, created_by_user_id=cls.admin.id),
                EmployeeTraining(employee_id=active.id, course_name="NR-35", training_type="Seguranca", ends_on=today, expires_on=today + timedelta(days=10), created_by_user_id=cls.admin.id),
            ])
            db.session.commit()
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(cls.admin)}"}
            cls.manager_headers = {"Authorization": f"Bearer {generate_token(cls.manager)}"}
            cls.driver_headers = {"Authorization": f"Bearer {generate_token(cls.driver)}"}
            cls.start = (today - timedelta(days=2)).isoformat()
            cls.end = today.isoformat()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        for path in (DB_PATH, Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm")):
            if path.exists():
                path.unlink()

    def test_dashboard_calculates_effective_attendance_and_alerts(self):
        response = self.client.get(f"/rh/gestao?data_inicial={self.start}&data_final={self.end}&dias_alerta=30", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()["data"]
        self.assertEqual(data["employees"]["active"], 1)
        self.assertEqual(data["employees"]["inactive"], 1)
        self.assertEqual(data["attendance"]["absences"], 1)
        self.assertEqual(data["attendance"]["absenteeism_percent"], 50.0)
        self.assertEqual({row["kind"] for row in data["alerts"]}, {"DOCUMENTO", "TREINAMENTO"})

    def test_manager_does_not_receive_sensitive_document_alert(self):
        response = self.client.get(f"/rh/gestao?data_inicial={self.start}&data_final={self.end}&dias_alerta=30", headers=self.manager_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        alerts = response.get_json()["data"]["alerts"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["kind"], "TREINAMENTO")

    def test_export_is_audited_and_driver_is_denied(self):
        denied = self.client.get("/rh/gestao", headers=self.driver_headers)
        self.assertEqual(denied.status_code, 403, denied.get_json())
        exported = self.client.post("/rh/gestao/exportacoes", headers=self.manager_headers, json={"format": "csv"})
        self.assertEqual(exported.status_code, 200, exported.get_json())
        with self.app.app_context():
            self.assertTrue(AuditLog.query.filter_by(entity_type="RH_MANAGEMENT", action="EXPORT").first())


if __name__ == "__main__":
    unittest.main()
