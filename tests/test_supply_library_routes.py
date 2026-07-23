from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path: sys.path.insert(0, str(BACKEND))
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_supply_library_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import EquipmentFamily, EquipmentProfile, MaintenanceMaterial, MaintenanceSchedule, MaintenanceScheduleItem, Material, User, Vehicle
from app.services.auth_service import generate_token


class SupplyLibraryRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists(): DB_PATH.unlink()
        cls.app = create_app(); cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            if not admin:
                admin = User(nome="Administrador Suprimentos", login="admin", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
            mechanic = User(nome="Mecanico Suprimentos", login="mecanico_supr", tipo="mecanico", ativo=True); mechanic.set_password("teste123")
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG SUPR", tipo="rtg", ativo=True)
            material = Material(referencia="MAT-SUPR", descricao="Mangueira hidráulica", aplicacao_tipo="ambos", quantidade_estoque=10, estoque_minimo=1, ativo=True)
            db.session.add_all([mechanic, vehicle, material]); db.session.flush()
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id))
            schedule = MaintenanceSchedule(source_type="PREVENTIVA", source_key="SUPR-TESTE", title="Teste de suprimento", status="PROGRAMADA", start_date=date.today(), end_date=date.today(), daily_capacity=1, created_by_user_id=admin.id, assigned_mechanic_user_id=mechanic.id)
            db.session.add(schedule); db.session.flush()
            item = MaintenanceScheduleItem(schedule_id=schedule.id, vehicle_id=vehicle.id, assigned_mechanic_user_id=mechanic.id, scheduled_date=date.today(), status="PROGRAMADO")
            db.session.add(item); db.session.flush()
            link = MaintenanceMaterial(schedule_id=schedule.id, material_id=material.id, quantity_per_vehicle=2, quantity_required=2, quantity_reserved=0, status="DISPONIVEL_EM_ESTOQUE")
            db.session.add(link); db.session.commit()
            cls.family_id, cls.vehicle_id, cls.material_id, cls.link_id, cls.item_id = family.id, vehicle.id, material.id, link.id, item.id
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.mechanic_headers = {"Authorization": f"Bearer {generate_token(mechanic)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context(): db.session.remove(); db.engine.dispose()
        if DB_PATH.exists(): DB_PATH.unlink()

    def test_warehouse_reservation_consumes_with_maintenance_os_and_document_is_found_by_vehicle(self):
        warehouse = self.client.post("/suprimentos/depositos", json={"code": "ALM-01", "name": "Almoxarifado central"}, headers=self.admin_headers)
        self.assertEqual(warehouse.status_code, 201, warehouse.get_json())
        warehouse_id = warehouse.get_json()["data"]["id"]
        stock = self.client.post("/suprimentos/estoques", json={"warehouse_id": warehouse_id, "material_id": self.material_id, "quantity": 10}, headers=self.admin_headers)
        self.assertEqual(stock.status_code, 201, stock.get_json())
        stock_id = stock.get_json()["data"]["id"]
        applications = self.client.put(f"/materiais/{self.material_id}/familias", json={"family_ids": [self.family_id]}, headers=self.admin_headers)
        self.assertEqual(applications.status_code, 200, applications.get_json())
        reservation = self.client.post("/suprimentos/reservas", json={"maintenance_material_id": self.link_id, "warehouse_stock_id": stock_id, "quantity": 2}, headers=self.admin_headers)
        self.assertEqual(reservation.status_code, 201, reservation.get_json())

        executed = self.client.put(f"/manutencao/itens/{self.item_id}", json={"status": "INSTALADO", "photo_after": "/uploads/evidence.jpg"}, headers=self.mechanic_headers)
        self.assertEqual(executed.status_code, 200, executed.get_json())
        stocks = self.client.get("/suprimentos/estoques", headers=self.admin_headers).get_json()["data"]
        self.assertEqual(stocks[0]["quantity"], 8)
        self.assertEqual(stocks[0]["reserved_quantity"], 0)
        self.assertEqual(stocks[0]["material"]["quantidade_estoque"], 8)

        created = self.client.post("/biblioteca-tecnica", json={"code": "MAN-RTG", "title": "Manual RTG", "document_type": "MANUAL", "revision": "A", "file_path": "/uploads/manual-rtg.pdf", "family_id": self.family_id}, headers=self.admin_headers)
        self.assertEqual(created.status_code, 201, created.get_json())
        docs = self.client.get(f"/biblioteca-tecnica?vehicle_id={self.vehicle_id}", headers=self.mechanic_headers)
        self.assertEqual(docs.status_code, 200, docs.get_json())
        self.assertEqual(docs.get_json()["data"][0]["code"], "MAN-RTG")

    def test_management_is_required_for_stock_and_documents(self):
        denied = self.client.post("/suprimentos/depositos", json={"code": "X", "name": "X"}, headers=self.mechanic_headers)
        self.assertEqual(denied.status_code, 403, denied.get_json())


if __name__ == "__main__": unittest.main()
