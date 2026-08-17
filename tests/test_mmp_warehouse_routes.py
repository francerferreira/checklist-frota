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

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_mmp_warehouse_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Material, User, Vehicle  # noqa: E402
from app.services.auth_service import generate_token  # noqa: E402


class MmpWarehouseRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin_mmp").first()
            if not admin:
                admin = User(nome="Admin MMP", login="admin_mmp", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
            operational = User(nome="Operacional MMP", login="operacional_mmp", tipo="operacional", ativo=True)
            operational.set_password("teste123")
            material = Material(referencia="MMP-TRANSFER-01", descricao="Filtro MMP", aplicacao_tipo="ambos", quantidade_estoque=10, estoque_minimo=1, ativo=True)
            vehicle = Vehicle(placa="MMP-01", modelo="RTG", frota="RTG-MMP-01", tipo="rtg", ativo=True)
            db.session.add_all([operational, material, vehicle])
            db.session.commit()
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.operational_headers = {"Authorization": f"Bearer {generate_token(operational)}"}
            cls.material_id, cls.vehicle_id = material.id, vehicle.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_transfer_from_main_warehouse_to_mmp_and_application_by_qr(self):
        principal = self.client.post("/suprimentos/depositos", json={"code": "ARM-PRINCIPAL", "name": "Armazém Principal", "warehouse_type": "PRINCIPAL"}, headers=self.admin_headers)
        mmp = self.client.post("/suprimentos/depositos", json={"code": "EST-MMP", "name": "Estoque MMP", "warehouse_type": "MMP"}, headers=self.admin_headers)
        self.assertEqual(principal.status_code, 201, principal.get_json())
        self.assertEqual(mmp.status_code, 201, mmp.get_json())
        principal_id = principal.get_json()["data"]["id"]
        mmp_id = mmp.get_json()["data"]["id"]

        source = self.client.post("/suprimentos/estoques", json={"warehouse_id": principal_id, "material_id": self.material_id, "quantity": 10}, headers=self.admin_headers)
        self.assertEqual(source.status_code, 201, source.get_json())
        location = self.client.post("/suprimentos/locais", json={"warehouse_id": mmp_id, "shelf_code": "PRATELEIRA 01", "location_code": "P1A", "position_code": "A"}, headers=self.admin_headers)
        self.assertEqual(location.status_code, 201, location.get_json())
        location_id = location.get_json()["data"]["id"]

        transfer = self.client.post("/suprimentos/transferencias", json={"items": [{"material_id": self.material_id, "quantity": 4, "location_id": location_id}]}, headers=self.admin_headers)
        self.assertEqual(transfer.status_code, 201, transfer.get_json())
        mmp_stock = self.client.get(f"/suprimentos/mmp/saldos", headers=self.operational_headers)
        self.assertEqual(mmp_stock.status_code, 200, mmp_stock.get_json())
        self.assertEqual(mmp_stock.get_json()["data"][0]["quantity"], 4)
        self.assertEqual(mmp_stock.get_json()["data"][0]["location"]["position_code"], "A")
        qr_code = mmp_stock.get_json()["data"][0]["qr_code"]

        lookup = self.client.get(f"/suprimentos/mmp/qr/{qr_code}", headers=self.operational_headers)
        self.assertEqual(lookup.status_code, 200, lookup.get_json())
        issued = self.client.post("/suprimentos/mmp/saidas", json={"qr_code": qr_code, "quantity": 2, "vehicle_id": self.vehicle_id, "application": "Troca preventiva"}, headers=self.operational_headers)
        self.assertEqual(issued.status_code, 200, issued.get_json())
        self.assertEqual(issued.get_json()["data"]["stock"]["quantity"], 2)

        principal_stock = self.client.get(f"/suprimentos/estoques?warehouse_id={principal_id}", headers=self.admin_headers).get_json()["data"]
        self.assertEqual(principal_stock[0]["quantity"], 6)

    def test_operational_cannot_create_transfer_or_location(self):
        denied_transfer = self.client.post("/suprimentos/transferencias", json={"items": []}, headers=self.operational_headers)
        denied_location = self.client.post("/suprimentos/locais", json={}, headers=self.operational_headers)
        self.assertEqual(denied_transfer.status_code, 403)
        self.assertEqual(denied_location.status_code, 403)


if __name__ == "__main__":
    unittest.main()
