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

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_global_search_routes_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import AutomationExecution, Employee, Material, User, Vehicle
from app.services.auth_service import generate_token


class GlobalSearchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            cls.admin = User(nome="Admin Busca", login="admin-busca-global", tipo="admin", ativo=True)
            cls.admin.set_password("SenhaSegura123!")
            cls.driver = User(nome="Motorista Busca", login="motorista-busca-global", tipo="motorista", ativo=True)
            cls.driver.set_password("SenhaSegura123!")
            db.session.add_all([cls.admin, cls.driver])
            db.session.flush()
            vehicle = Vehicle(frota="ABC-001", placa="ABC1D23", modelo="Cavalo Busca", tipo="cavalo", ativo=True)
            material = Material(referencia="MAT-ABC", descricao="Filtro de busca", aplicacao_tipo="ambos", quantidade_estoque=2, estoque_minimo=1, ponto_reposicao=1, ativo=True)
            employee = Employee(registration="RH-ABC", full_name="Colaborador Busca", function_name="Mecanico", team_name="Equipe A", shift_name="1 turno", status="ATIVO")
            db.session.add_all([vehicle, material, employee])
            db.session.flush()
            db.session.add(AutomationExecution(rule_code="ESTOQUE_ABAIXO_MINIMO", entity_type="MATERIAL", entity_id=material.id, dedup_key="teste-busca-material", severity="ALTA", status="ATIVO", message="Alerta global para filtro de busca."))
            db.session.commit()
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(cls.admin)}"}
            cls.driver_headers = {"Authorization": f"Bearer {generate_token(cls.driver)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        for path in (DB_PATH, Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm")):
            if path.exists():
                path.unlink()

    def test_admin_finds_records_and_keeps_navigation_target(self):
        response = self.client.get("/navegacao/busca-global?q=ABC", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()["data"]
        self.assertTrue(any(row["kind"] == "EQUIPAMENTO" and row["page_key"] == "equipment" for row in rows))
        self.assertTrue(any(row["kind"] == "MATERIAL" and row["page_key"] == "materials" for row in rows))
        self.assertTrue(any(row["kind"] == "COLABORADOR" and row["page_key"] == "employees" for row in rows))

    def test_alert_search_opens_only_a_permitted_context(self):
        response = self.client.get("/navegacao/busca-global?q=Alerta", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        alert = next(row for row in response.get_json()["data"] if row["kind"] == "ALERTA")
        self.assertEqual(alert["page_key"], "materials")

    def test_driver_cannot_search_records_outside_dashboard_and_short_query_is_rejected(self):
        response = self.client.get("/navegacao/busca-global?q=ABC", headers=self.driver_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["data"], [])
        short = self.client.get("/navegacao/busca-global?q=A", headers=self.admin_headers)
        self.assertEqual(short.status_code, 400, short.get_json())


if __name__ == "__main__":
    unittest.main()
