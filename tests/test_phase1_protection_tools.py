from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Phase1ProtectionToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema_tool = _load_module("compare_database_schema", ROOT / "tools" / "compare_database_schema.py")
        cls.restore_tool = _load_module("restore_backup_archive", ROOT / "tools" / "restore_backup_archive.py")

    def test_schema_comparison_detects_structural_drift(self):
        metadata = sa.MetaData()
        sa.Table(
            "assets",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("code", sa.String(20), nullable=False, unique=True, index=True),
        )
        engine = sa.create_engine("sqlite:///:memory:")
        metadata.create_all(engine)
        with engine.connect() as connection:
            report = self.schema_tool.compare_schema(connection, metadata)
            self.assertEqual([], report["issues"])
            connection.execute(sa.text("ALTER TABLE assets ADD COLUMN legacy_value VARCHAR(20)"))
            report = self.schema_tool.compare_schema(connection, metadata)
            self.assertTrue(
                any(
                    item["category"] == "column_only_database" and item.get("column") == "legacy_value"
                    for item in report["issues"]
                )
            )
        engine.dispose()

    def test_backup_validation_and_isolated_restore(self):
        metadata = sa.MetaData()
        assets = sa.Table(
            "assets",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("code", sa.String(20), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backup_path = root / "backup.zip"
            manifest = {
                "generated_at": "2026-07-17T10:00:00",
                "tables": {"assets": 1},
                "photos": [{"path": "ativos/evidencia.jpg", "size": 4}],
            }
            rows = [{"id": 1, "code": "RTG 01", "created_at": "2026-07-17T09:00:00"}]
            with zipfile.ZipFile(backup_path, "w") as archive:
                archive.writestr("backup_manifesto.json", json.dumps(manifest))
                archive.writestr("banco/assets.json", json.dumps(rows))
                archive.writestr("fotos/ativos/evidencia.jpg", b"test")

            validation = self.restore_tool.validate_backup(backup_path)
            self.assertEqual(1, validation["tables"])
            self.assertEqual(1, validation["rows"])
            result = self.restore_tool.restore_backup(backup_path, root / "restore", metadata)
            self.assertEqual(1, result["rows"])
            self.assertTrue(Path(result["database_path"]).exists())
            self.assertTrue((root / "restore" / "uploads" / "ativos" / "evidencia.jpg").exists())
            with self.assertRaises(self.restore_tool.BackupValidationError):
                self.restore_tool.restore_backup(backup_path, root / "restore", metadata)

            engine = sa.create_engine(f"sqlite:///{result['database_path']}")
            with engine.connect() as connection:
                row = connection.execute(sa.select(assets)).mappings().one()
                self.assertEqual("RTG 01", row["code"])
                self.assertEqual(datetime(2026, 7, 17, 9, 0), row["created_at"])
            engine.dispose()

    def test_cloud_backup_scripts_do_not_store_default_password(self):
        powershell = (ROOT / "backup_checklist_cloud.ps1").read_text(encoding="utf-8")
        batch = (ROOT / "backup_checklist_cloud.bat").read_text(encoding="utf-8")
        self.assertNotIn("123456", powershell)
        self.assertNotIn("123456", batch)
        self.assertNotIn('set "SENHA=', batch)
        self.assertIn("$loginResponse.data.token", powershell)
        self.assertIn("$statusResponse.data", powershell)
        self.assertIn("$backupResponse.data", powershell)


if __name__ == "__main__":
    unittest.main()
