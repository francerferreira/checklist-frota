from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_purchase_import_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import Material, PurchaseImportBatch, PurchaseInvoice, PurchaseOrder, PurchaseRequest, PurchaseRequestItem, User
from app.services.purchase_import_service import SOURCE_COLUMNS, import_purchase_workbook


class PurchaseImportServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.temp_source = Path(tempfile.gettempdir()) / "purchase_import_source_test.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(SOURCE_COLUMNS)
        sheet.append([2, 1, datetime(2026, 8, 1), "000001", "100-REQ", "Compra RTG", "003.000.001", "Filtro", "Marca", "REF", "PN", 3, None, "1.1.40", "200-BUYER", "000010", datetime(2026, 8, 2), 3, "1.2.51", "Fornecedor A", "1", "99", datetime(2026, 8, 4), 3, 2, 120.5])
        sheet.append([2, 1, datetime(2026, 8, 1), "000001", "100-REQ", "Compra RTG", "017.001.000001", "Serviço de manutenção", None, None, None, 1, None, "1.1.40", "200-BUYER", "000010", datetime(2026, 8, 2), 1, "1.2.51", "Fornecedor A", "1", "99", datetime(2026, 8, 4), 1, 1, 300])
        sheet.append([2, 1, datetime(2026, 8, 2), "000002", "101-REQ", "Compra LBS", "003.000.002", "Bomba", None, None, None, 2, None, "1.1.40", "200-BUYER", None, None, None, None, None, None, None, None, None, 0, 0])
        workbook.save(cls.temp_source)
        workbook.close()
        with cls.app.app_context():
            user = User(nome="Admin Importacao", login="admin_importacao", tipo="admin", ativo=True)
            user.set_password("teste123")
            db.session.add(user)
            db.session.commit()
            cls.user_id = user.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()
        if cls.temp_source.exists():
            cls.temp_source.unlink()

    def test_import_is_idempotent_and_links_material_pc_nf(self):
        with self.app.app_context():
            result = import_purchase_workbook(self.temp_source, user_id=self.user_id)
            self.assertEqual(result["status"], "CONCLUIDO")
            self.assertEqual(result["reconciliation"]["source_rows"], 3)
            self.assertEqual(result["reconciliation"]["purchase_requests"], 2)
            self.assertEqual(result["reconciliation"]["materials"], 2)
            self.assertEqual(result["reconciliation"]["services"], 1)
            self.assertEqual(PurchaseRequest.query.filter_by(imported=True, import_batch_id=result["batch"]["id"]).count(), 2)
            self.assertEqual(PurchaseRequestItem.query.filter_by(imported=True).count(), 3)
            self.assertEqual(PurchaseOrder.query.filter_by(imported=True, import_batch_id=result["batch"]["id"]).count(), 1)
            self.assertEqual(PurchaseInvoice.query.filter_by(imported=True, import_batch_id=result["batch"]["id"]).count(), 1)
            self.assertGreaterEqual(Material.query.filter(Material.referencia.like("003.%")).count(), 2)
            self.assertEqual(PurchaseImportBatch.query.filter_by(source_checksum=result["batch"]["source_checksum"]).count(), 1)

            second = import_purchase_workbook(self.temp_source, user_id=self.user_id)
            self.assertEqual(second["status"], "JA_IMPORTADO")
            self.assertEqual(PurchaseRequest.query.filter_by(imported=True, import_batch_id=result["batch"]["id"]).count(), 2)
            self.assertEqual(PurchaseRequestItem.query.filter_by(imported=True).count(), 3)


if __name__ == "__main__":
    unittest.main()
