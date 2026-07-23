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
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_purchase_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import Material, User
from app.services.auth_service import generate_token


class PurchaseRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User(nome="Administrador Compras", login="admin_compras", tipo="admin", ativo=True)
            admin.set_password("teste123")
            gestor = User(nome="Gestor Compras", login="gestor_compras", tipo="gestor", ativo=True)
            gestor.set_password("teste123")
            material = Material(referencia="MAT-COMPRA", descricao="Kit hidráulico", aplicacao_tipo="ambos", quantidade_estoque=0, estoque_minimo=2)
            db.session.add_all([admin, gestor, material])
            db.session.commit()
            cls.material_id = material.id
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.gestor_headers = {"Authorization": f"Bearer {generate_token(gestor)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_purchase_request_approval_partial_receipt_and_idempotency(self):
        supplier = self.client.post(
            "/compras/fornecedores",
            headers=self.gestor_headers,
            json={"code": "FOR-001", "name": "Fornecedor Hidráulico", "email": "compras@example.test"},
        )
        self.assertEqual(supplier.status_code, 201, supplier.get_json())
        supplier_id = supplier.get_json()["data"]["id"]

        request = self.client.post(
            "/compras/solicitacoes",
            headers=self.gestor_headers,
            json={
                "material_id": self.material_id,
                "supplier_id": supplier_id,
                "requested_quantity": 5,
                "priority": "CRITICA",
                "expected_date": (date.today() + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(request.status_code, 201, request.get_json())
        purchase = request.get_json()["data"]

        gestor_approval = self.client.post(f"/compras/solicitacoes/{purchase['id']}/aprovar", headers=self.gestor_headers)
        self.assertEqual(gestor_approval.status_code, 403, gestor_approval.get_json())
        approved = self.client.post(f"/compras/solicitacoes/{purchase['id']}/aprovar", headers=self.admin_headers)
        self.assertEqual(approved.status_code, 200, approved.get_json())

        first_receipt = self.client.post(
            f"/compras/solicitacoes/{purchase['id']}/recebimentos",
            headers=self.gestor_headers,
            json={"quantity": 2, "idempotency_key": "rcv-purchase-001"},
        )
        self.assertEqual(first_receipt.status_code, 200, first_receipt.get_json())
        self.assertEqual(first_receipt.get_json()["data"]["status"], "PARCIALMENTE_RECEBIDA")

        duplicate = self.client.post(
            f"/compras/solicitacoes/{purchase['id']}/recebimentos",
            headers=self.gestor_headers,
            json={"quantity": 2, "idempotency_key": "rcv-purchase-001"},
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        self.assertEqual(duplicate.get_json()["data"]["received_quantity"], 2)

        final_receipt = self.client.post(
            f"/compras/solicitacoes/{purchase['id']}/recebimentos",
            headers=self.gestor_headers,
            json={"quantity": 3, "idempotency_key": "rcv-purchase-002"},
        )
        self.assertEqual(final_receipt.status_code, 200, final_receipt.get_json())
        self.assertEqual(final_receipt.get_json()["data"]["status"], "RECEBIDA")
        with self.app.app_context():
            self.assertEqual(db.session.get(Material, self.material_id).quantidade_estoque, 5)


if __name__ == "__main__":
    unittest.main()
