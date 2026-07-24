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

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_employee_records_routes_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import Employee, EmployeeHistoryEvent, EmployeeTraining, User
from app.services.auth_service import generate_token


class EmployeeRecordsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            cls.admin = User(nome="Admin RH", login="admin-rh-registros", tipo="admin", ativo=True)
            cls.admin.set_password("SenhaSegura123!")
            cls.manager = User(nome="Gestor RH", login="gestor-rh-registros", tipo="gestor", ativo=True)
            cls.manager.set_password("SenhaSegura123!")
            cls.driver = User(nome="Motorista RH", login="motorista-rh-registros", tipo="motorista", ativo=True)
            cls.driver.set_password("SenhaSegura123!")
            db.session.add_all([cls.admin, cls.manager, cls.driver])
            db.session.flush()
            employee = Employee(registration="RH-REG-001", full_name="Colaborador Registros", function_name="Mecanico", team_name="Equipe A", shift_name="1 turno", status="ATIVO", user_id=cls.driver.id)
            db.session.add(employee)
            db.session.commit()
            cls.employee_id = employee.id
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(cls.admin)}"}
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

    def test_sensitive_document_is_admin_only_and_hidden_from_manager(self):
        regular = self.client.post("/rh/documentos", headers=self.manager_headers, json={"employee_id": self.employee_id, "document_type": "CNH", "file_path": "/uploads/rh/cnh.pdf", "expires_on": "2027-07-24"})
        self.assertEqual(regular.status_code, 201, regular.get_json())
        denied = self.client.post("/rh/documentos", headers=self.manager_headers, json={"employee_id": self.employee_id, "document_type": "ASO", "file_path": "/uploads/rh/aso.pdf", "is_sensitive": True})
        self.assertEqual(denied.status_code, 400, denied.get_json())
        sensitive = self.client.post("/rh/documentos", headers=self.admin_headers, json={"employee_id": self.employee_id, "document_type": "ASO", "file_path": "/uploads/rh/aso.pdf", "is_sensitive": True})
        self.assertEqual(sensitive.status_code, 201, sensitive.get_json())
        manager_rows = self.client.get("/rh/documentos", headers=self.manager_headers).get_json()["data"]
        admin_rows = self.client.get("/rh/documentos", headers=self.admin_headers).get_json()["data"]
        self.assertEqual(len(manager_rows), 1)
        self.assertEqual(len(admin_rows), 2)
        self.assertFalse(manager_rows[0]["is_sensitive"])

    def test_training_and_functional_history_are_recorded(self):
        training = self.client.post("/rh/treinamentos", headers=self.manager_headers, json={"employee_id": self.employee_id, "course_name": "Trabalho em altura", "training_type": "NR-35", "ends_on": "2026-07-24", "expires_on": "2027-07-24", "workload_hours": 8, "certificate_path": "/uploads/rh/nr35.pdf"})
        self.assertEqual(training.status_code, 201, training.get_json())
        self.assertEqual(training.get_json()["data"]["status"], "VALIDO")
        history = self.client.post("/rh/historico", headers=self.manager_headers, json={"employee_id": self.employee_id, "event_type": "MUDANCA_DE_FUNCAO", "occurred_on": "2026-07-24", "description": "Transferido para manutencao preventiva."})
        self.assertEqual(history.status_code, 201, history.get_json())
        rows = self.client.get(f"/rh/historico?colaborador_id={self.employee_id}", headers=self.manager_headers).get_json()["data"]
        self.assertEqual(len(rows), 1)
        with self.app.app_context():
            self.assertEqual(EmployeeTraining.query.count(), 1)
            self.assertEqual(EmployeeHistoryEvent.query.count(), 1)

    def test_profile_without_hr_management_access_is_denied(self):
        response = self.client.get("/rh/documentos", headers=self.driver_headers)
        self.assertEqual(response.status_code, 403, response.get_json())


if __name__ == "__main__":
    unittest.main()
