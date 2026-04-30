from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_audit_service_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.services import audit_service


class _FailingBeginContext:
    def __enter__(self):
        raise RuntimeError("falha simulada")

    def __exit__(self, exc_type, exc, tb):
        return False


class AuditServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            audit_service.db.session.remove()
            audit_service.db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def test_after_commit_logs_exception_when_persist_fails(self):
        session = type("FakeSession", (), {"info": {"_audit_pending_rows": [{"entity_id": 1}]}})()

        with self.app.app_context():
            with patch.object(audit_service.db.engine, "begin", return_value=_FailingBeginContext()), patch.object(
                audit_service.LOGGER, "exception"
            ) as logger_exception:
                audit_service._after_commit(session)

        logger_exception.assert_called_once()
        self.assertIsNone(session.info.get("_audit_pending_rows"))


if __name__ == "__main__":
    unittest.main()
