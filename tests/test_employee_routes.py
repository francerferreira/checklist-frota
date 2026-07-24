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

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_employee_routes_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import Employee, User
from app.services.auth_service import generate_token


class EmployeeRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            cls.admin = User(nome="Admin RH", login="admin-rh", tipo="admin", ativo=True)
            cls.admin.set_password("SenhaSegura123!")
            cls.manager = User(nome="Gestor RH", login="gestor-rh", tipo="gestor", ativo=True)
            cls.manager.set_password("SenhaSegura123!")
            cls.driver = User(nome="Motorista RH", login="motorista-rh", tipo="motorista", ativo=True)
            cls.driver.set_password("SenhaSegura123!")
            db.session.add_all([cls.admin, cls.manager, cls.driver])
            db.session.commit()
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

    def test_management_can_create_update_and_list_employee(self):
        created = self.client.post(
            "/rh/colaboradores",
            headers=self.manager_headers,
            json={
                "registration": "RH-001",
                "full_name": "Ana da Silva",
                "function_name": "Mecânica",
                "team_name": "Manutenção A",
                "shift_name": "1º turno",
                "status": "ATIVO",
                "hired_on": "2026-07-24",
                "user_id": self.driver.id,
                "photo_path": "/uploads/ana-rh.jpg",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        employee = created.get_json()["data"]
        self.assertEqual(employee["registration"], "RH-001")
        self.assertEqual(employee["linked_user"]["login"], "motorista-rh")

        listed = self.client.get("/rh/colaboradores?busca=Ana", headers=self.manager_headers)
        self.assertEqual(listed.status_code, 200, listed.get_json())
        self.assertEqual(len(listed.get_json()["data"]), 1)

        updated = self.client.put(
            f"/rh/colaboradores/{employee['id']}",
            headers=self.admin_headers,
            json={
                "registration": "RH-001",
                "full_name": "Ana da Silva",
                "function_name": "Mecânica Especialista",
                "team_name": "Manutenção A",
                "shift_name": "2º turno",
                "status": "ATIVO",
                "hired_on": "2026-07-24",
                "user_id": self.driver.id,
                "photo_path": "/uploads/ana-rh.jpg",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["data"]["shift_name"], "2º turno")

    def test_profile_without_management_access_is_denied(self):
        response = self.client.get("/rh/colaboradores", headers=self.driver_headers)
        self.assertEqual(response.status_code, 403, response.get_json())

    def test_same_login_cannot_be_linked_twice(self):
        with self.app.app_context():
            if not Employee.query.filter_by(user_id=self.driver.id).first():
                db.session.add(
                    Employee(
                        registration="RH-BASE",
                        full_name="Colaborador base",
                        function_name="Auxiliar",
                        team_name="Manutenção B",
                        shift_name="3º turno",
                        status="ATIVO",
                        user_id=self.driver.id,
                    )
                )
                db.session.commit()
        response = self.client.post(
            "/rh/colaboradores",
            headers=self.admin_headers,
            json={
                "registration": "RH-002",
                "full_name": "Outro colaborador",
                "function_name": "Auxiliar",
                "team_name": "Manutenção B",
                "shift_name": "3º turno",
                "status": "PRE_CADASTRO",
                "user_id": self.driver.id,
            },
        )
        self.assertEqual(response.status_code, 409, response.get_json())


if __name__ == "__main__":
    unittest.main()
