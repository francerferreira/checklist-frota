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

TEST_ROOT = Path(tempfile.gettempdir()) / "checklist_frota_local_homologation_test"
DB_PATH = TEST_ROOT / "checklist_frota.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from tools.validate_local_homologation import run_local_homologation


class LocalHomologationToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TEST_ROOT.exists():
            import shutil

            shutil.rmtree(TEST_ROOT)
        TEST_ROOT.mkdir(parents=True)
        cls.app = create_app()
        cls.app.config["BACKUP_FOLDER"] = TEST_ROOT / "backups"

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_ROOT.exists():
            import shutil

            shutil.rmtree(TEST_ROOT)

    def test_local_homologation_creates_and_restores_a_valid_backup(self):
        with self.app.app_context():
            result = run_local_homologation(self.app)

        self.assertTrue(result["ready"])
        self.assertEqual(result["health"]["status"], "ok")
        self.assertEqual(result["source"]["integrity"], "ok")
        self.assertEqual(result["restore"]["integrity"], "ok")
        self.assertEqual(result["source"]["tables"], result["restore"]["tables"])
        self.assertGreater(result["backup"]["tables"], 0)
        self.assertTrue((TEST_ROOT / "backups" / result["backup"]["filename"]).exists())


if __name__ == "__main__":
    unittest.main()
