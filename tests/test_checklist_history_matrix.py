from __future__ import annotations

import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_history_matrix_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import Checklist, ChecklistItem, User, Vehicle
from app.services.auth_service import generate_token


class ChecklistHistoryMatrixTests(unittest.TestCase):
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

    def _create_vehicle(self, *, tipo: str = "carreta", ativo: bool = True, frota_prefix: str = "FROTA") -> Vehicle:
        suffix = uuid.uuid4().hex[:6].upper()
        vehicle = Vehicle(
            frota=f"{frota_prefix}-{suffix}",
            tipo=tipo,
            placa=f"ABC-{suffix}",
            ano="2024",
            modelo="MODELO TESTE",
            chassi=f"CHASSI-{suffix}",
            configuracao="",
            atividade="OPERACAO",
            status="ON",
            local="",
            descricao="",
            ativo=ativo,
        )
        db.session.add(vehicle)
        db.session.commit()
        return vehicle

    def _create_checklist(self, vehicle_id: int, *, created_at: datetime, item_name: str = "FREIOS", status: str = "OK") -> Checklist:
        checklist = Checklist(
            vehicle_id=vehicle_id,
            user_id=self.admin_id,
            created_at=created_at,
        )
        db.session.add(checklist)
        db.session.flush()
        db.session.add(
            ChecklistItem(
                checklist_id=checklist.id,
                item_nome=item_name,
                status=status,
                created_at=created_at,
            )
        )
        db.session.commit()
        return checklist

    def test_history_matrix_returns_latest_checklist_text_per_day_and_total_count(self):
        with self.app.app_context():
            vehicle = self._create_vehicle(tipo="carreta", frota_prefix="CARRETA")
            self._create_checklist(vehicle.id, created_at=datetime(2026, 4, 20, 8, 10))
            self._create_checklist(vehicle.id, created_at=datetime(2026, 4, 20, 14, 35))
            self._create_checklist(vehicle.id, created_at=datetime(2026, 4, 21, 6, 45))

        response = self.client.get(
            "/checklist/historico-matriz?tipo=carreta&data_inicio=2026-04-20&data_fim=2026-04-21",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json() or {}
        self.assertTrue(payload.get("success"))
        data = payload.get("data") or {}
        self.assertEqual(data.get("periodo"), {"inicio": "2026-04-20", "fim": "2026-04-21"})
        self.assertEqual(
            data.get("columns"),
            [
                {"date": "2026-04-20", "label": "20/04"},
                {"date": "2026-04-21", "label": "21/04"},
            ],
        )
        self.assertEqual(len(data.get("rows") or []), 1)
        row = data["rows"][0]
        self.assertEqual(row["tipo"], "carreta")
        self.assertEqual(row["modelo"], "MODELO TESTE")
        self.assertIn("descricao", row)
        self.assertEqual(row["checklist_count"], 3)
        self.assertEqual(len(row["cell_details"][0]), 2)
        self.assertEqual(row["cell_details"][0][1]["time"], "14:35")
        self.assertEqual(row["cells"][0], "14:35 - Administrador")
        self.assertEqual(row["cells"][1], "06:45 - Administrador")

        detail_response = self.client.get(
            f"/checklists/{row['cell_details'][0][0]['id']}",
            headers=self.headers,
        )
        detail_payload = detail_response.get_json() or {}
        self.assertTrue(detail_payload.get("success"))
        self.assertIn("itens", detail_payload.get("data") or {})

    def test_history_matrix_excludes_inactive_and_non_matching_vehicle_types(self):
        with self.app.app_context():
            active_carreta = self._create_vehicle(tipo="carreta", ativo=True, frota_prefix="ATIVA")
            inactive_carreta = self._create_vehicle(tipo="carreta", ativo=False, frota_prefix="INATIVA")
            cavalo = self._create_vehicle(tipo="cavalo", ativo=True, frota_prefix="CAVALO")
            self._create_checklist(active_carreta.id, created_at=datetime(2026, 4, 20, 9, 0))
            self._create_checklist(inactive_carreta.id, created_at=datetime(2026, 4, 20, 10, 0))
            self._create_checklist(cavalo.id, created_at=datetime(2026, 4, 20, 11, 0))

        response = self.client.get(
            "/checklist/historico-matriz?tipo=carreta&data_inicio=2026-04-20&data_fim=2026-04-20",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json() or {}
        rows = (payload.get("data") or {}).get("rows") or []
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["frota"].startswith("ATIVA-"))

    def test_history_matrix_rejects_invalid_date_ranges(self):
        response = self.client.get(
            "/checklist/historico-matriz?data_inicio=2026-04-25&data_fim=2026-04-20",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400, response.get_json())
        payload = response.get_json() or {}
        self.assertFalse(payload.get("success", True))
        self.assertIn("data final", payload.get("error", "").lower())


if __name__ == "__main__":
    unittest.main()
