from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_grouped_submission_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Checklist, ChecklistItem, User, Vehicle  # noqa: E402
from app.services.auth_service import generate_token  # noqa: E402
from app.services.checklist_catalog import get_items_for_vehicle_type  # noqa: E402


class ChecklistGroupedSubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            assert admin is not None
            cls.admin_id = admin.id
            cls.headers = {"Authorization": f"Bearer {generate_token(admin)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        with self.app.app_context():
            ChecklistItem.query.delete()
            Checklist.query.delete()
            Vehicle.query.delete()
            db.session.commit()

    def test_submit_checklist_records_grouping_metadata_for_side_item(self):
        with self.app.app_context():
            vehicle = Vehicle(
                frota="GRUPO-001",
                tipo="cavalo",
                placa="GRP-0001",
                ano="2026",
                modelo="MODELO TESTE",
                chassi="CHASSI-GRUPO-001",
                configuracao="",
                atividade="OPERACAO",
                status="ON",
                local="",
                descricao="",
                ativo=True,
            )
            db.session.add(vehicle)
            db.session.commit()
            vehicle_id = vehicle.id
            expected_items = get_items_for_vehicle_type("cavalo")

        payload_items = []
        for item_name in expected_items:
            row = {"item_nome": item_name, "status": "OK"}
            if item_name == "PARALAMAS DIREITO":
                row.update(
                    {
                        "status": "NC",
                        "observacao": "Teste agrupado",
                        "foto_antes": "/uploads/teste/paralamas-direito.jpg",
                    }
                )
            payload_items.append(row)

        response = self.client.post(
            "/checklist",
            json={"vehicle_id": vehicle_id, "itens": payload_items},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 201, response.get_json())
        payload = response.get_json() or {}
        item = next(
            row
            for row in (payload.get("data") or {}).get("itens", [])
            if row["item_nome"] == "PARALAMAS DIREITO"
        )
        self.assertEqual(item["item_principal"], "PARALAMAS")
        self.assertEqual(item["parte"], "LADO DIREITO")
        self.assertEqual(item["item_label"], "PARALAMAS - LADO DIREITO")
        self.assertEqual(item["tipo_agrupamento"], "lado")
        self.assertEqual(item["item_origem"], "PARALAMAS DIREITO")

        macro_response = self.client.get("/relatorios/macro", headers=self.headers)
        self.assertEqual(macro_response.status_code, 200, macro_response.get_json())
        macro_rows = (macro_response.get_json() or {}).get("data") or []
        self.assertTrue(any(row["item_nome"] == "PARALAMAS" for row in macro_rows))


if __name__ == "__main__":
    unittest.main()
