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

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_grouping_schema_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from sqlalchemy import inspect, text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Checklist, User, Vehicle  # noqa: E402
from app.services.runtime_schema_service import ensure_runtime_schema  # noqa: E402


class ChecklistGroupingSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def test_runtime_schema_backfills_grouping_columns_for_old_checklist_items_table(self):
        with self.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            self.assertIsNotNone(admin)
            vehicle = Vehicle(
                frota="AGRUP-001",
                tipo="cavalo",
                placa="AGR-0001",
                ano="2026",
                modelo="MODELO TESTE",
                chassi="CHASSI-AGRUP-001",
                configuracao="",
                atividade="OPERACAO",
                status="ON",
                local="",
                descricao="",
                ativo=True,
            )
            db.session.add(vehicle)
            db.session.flush()
            checklist = Checklist(vehicle_id=vehicle.id, user_id=admin.id)
            db.session.add(checklist)
            db.session.flush()
            checklist_id = checklist.id
            db.session.commit()

            db.session.execute(text("DROP TABLE checklist_items"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE checklist_items (
                        id INTEGER PRIMARY KEY,
                        checklist_id INTEGER NOT NULL,
                        item_nome VARCHAR(160) NOT NULL,
                        status VARCHAR(2) NOT NULL,
                        observacao TEXT,
                        foto_antes VARCHAR(255),
                        foto_depois VARCHAR(255),
                        codigo_peca VARCHAR(80),
                        descricao_peca VARCHAR(255),
                        resolved_by_user_id INTEGER,
                        resolvido BOOLEAN NOT NULL DEFAULT 0,
                        data_resolucao DATETIME,
                        created_at DATETIME NOT NULL
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO checklist_items
                    (id, checklist_id, item_nome, status, resolvido, created_at)
                    VALUES (1, :checklist_id, 'PARALAMAS DIREITO', 'NC', 0, CURRENT_TIMESTAMP)
                    """
                ),
                {"checklist_id": checklist_id},
            )
            db.session.commit()

            ensure_runtime_schema()

            columns = {column["name"] for column in inspect(db.engine).get_columns("checklist_items")}
            self.assertIn("item_principal", columns)
            self.assertIn("parte", columns)
            self.assertIn("tipo_agrupamento", columns)
            self.assertIn("item_origem", columns)

            row = db.session.execute(
                text(
                    """
                    SELECT item_nome, item_principal, parte, tipo_agrupamento, item_origem
                    FROM checklist_items
                    WHERE id = 1
                    """
                )
            ).mappings().one()
            self.assertEqual(row["item_nome"], "PARALAMAS DIREITO")
            self.assertEqual(row["item_principal"], "PARALAMAS")
            self.assertEqual(row["parte"], "LADO DIREITO")
            self.assertEqual(row["tipo_agrupamento"], "lado")
            self.assertEqual(row["item_origem"], "PARALAMAS DIREITO")


if __name__ == "__main__":
    unittest.main()
