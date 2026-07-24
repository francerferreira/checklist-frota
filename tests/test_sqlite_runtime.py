from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

TEST_ROOT = Path(tempfile.gettempdir()) / "checklist_frota_sqlite_runtime_test"
DB_PATH = TEST_ROOT / "checklist_frota.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
os.environ["SQLITE_BUSY_TIMEOUT_MS"] = "3000"
os.environ["SQLITE_JOURNAL_MODE"] = "WAL"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.services.sqlite_runtime_service import sqlite_runtime_status


class SQLiteRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TEST_ROOT.exists():
            import shutil

            shutil.rmtree(TEST_ROOT)
        TEST_ROOT.mkdir(parents=True)
        cls.app = create_app()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_ROOT.exists():
            import shutil

            shutil.rmtree(TEST_ROOT)

    def test_health_exposes_sqlite_runtime_protections(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200, response.get_json())
        sqlite_status = response.get_json()["sqlite"]
        self.assertTrue(sqlite_status["enabled"])
        self.assertEqual(sqlite_status["journal_mode"], "WAL")
        self.assertEqual(sqlite_status["busy_timeout_ms"], 3000)
        self.assertTrue(sqlite_status["foreign_keys"])

    def test_second_writer_waits_for_the_local_lock(self):
        with self.app.app_context():
            db.session.execute(text("CREATE TABLE IF NOT EXISTS runtime_concurrency_probe (id INTEGER PRIMARY KEY, value TEXT)"))
            db.session.commit()
            lock_connection = sqlite3.connect(DB_PATH, isolation_level=None, check_same_thread=False)
            lock_connection.execute("BEGIN IMMEDIATE")

            def release_lock():
                time.sleep(0.2)
                lock_connection.execute("COMMIT")
                lock_connection.close()

            release_thread = threading.Thread(target=release_lock)
            release_thread.start()
            started_at = time.monotonic()
            try:
                db.session.execute(text("INSERT INTO runtime_concurrency_probe (value) VALUES ('concurrent-write')"))
                db.session.commit()
            finally:
                release_thread.join()

            elapsed = time.monotonic() - started_at
            self.assertGreaterEqual(elapsed, 0.15)
            self.assertLess(elapsed, 3)
            self.assertEqual(sqlite_runtime_status()["busy_timeout_ms"], 3000)


if __name__ == "__main__":
    unittest.main()
