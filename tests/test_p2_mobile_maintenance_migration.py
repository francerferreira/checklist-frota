from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
PHASE_11_MIGRATION = ROOT / "migrations" / "versions" / "20260713_0009_mobile_asset_operations_phase_11.py"
P2_MIGRATION = ROOT / "migrations" / "versions" / "20260724_0011_mobile_maintenance_operations_p2.py"


def load_migration(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class P2MobileMaintenanceMigrationTests(unittest.TestCase):
    def test_upgrade_accepts_new_mobile_operation_and_downgrade_restores_previous_rule(self):
        path = Path(tempfile.gettempdir()) / "checklist_frota_p2_mobile_maintenance_migration.db"
        if path.exists():
            path.unlink()
        engine = sa.create_engine(f"sqlite:///{path}")
        metadata = sa.MetaData()
        users = sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
        vehicles = sa.Table("vehicles", metadata, sa.Column("id", sa.Integer, primary_key=True))
        metadata.create_all(engine)
        phase_11 = load_migration(PHASE_11_MIGRATION, "phase_11_mobile_operations")
        p2 = load_migration(P2_MIGRATION, "p2_mobile_maintenance")

        with engine.begin() as connection:
            occurred_at = datetime(2026, 7, 24, 12, 0, 0)
            connection.execute(users.insert(), [{"id": 1}])
            connection.execute(vehicles.insert(), [{"id": 1}])
            phase_11.op = Operations(MigrationContext.configure(connection))
            phase_11.upgrade()
            p2.op = Operations(MigrationContext.configure(connection))
            p2.upgrade()
            operations = sa.Table("mobile_sync_operations", sa.MetaData(), autoload_with=connection)
            connection.execute(operations.insert(), {
                "operation_id": "migration-mobile-maintenance-01",
                "operation_type": "MANUTENCAO_ATUALIZAR_ITEM",
                "vehicle_id": 1,
                "user_id": 1,
                "payload_hash": "a" * 64,
                "status": "PROCESSANDO",
                "occurred_at": occurred_at,
                "created_at": occurred_at,
            })
            with self.assertRaises(RuntimeError):
                p2.downgrade()
            connection.execute(
                operations.delete().where(operations.c.operation_type == "MANUTENCAO_ATUALIZAR_ITEM")
            )
            p2.downgrade()
            with self.assertRaises(sa.exc.IntegrityError):
                connection.execute(operations.insert(), {
                    "operation_id": "migration-mobile-maintenance-02",
                    "operation_type": "MANUTENCAO_ATUALIZAR_ITEM",
                    "vehicle_id": 1,
                    "user_id": 1,
                    "payload_hash": "b" * 64,
                    "status": "PROCESSANDO",
                    "occurred_at": occurred_at,
                    "created_at": occurred_at,
                })
        engine.dispose()
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    unittest.main()
