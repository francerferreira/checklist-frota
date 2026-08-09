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

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_hourmeter_schema_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from sqlalchemy import inspect, text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.services.runtime_schema_service import ensure_runtime_schema  # noqa: E402


class HourmeterRuntimeSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def test_runtime_schema_upgrades_legacy_hourmeter_table(self):
        with self.app.app_context():
            db.session.execute(text("DROP TABLE hourmeter_readings"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE hourmeter_readings (
                        id INTEGER PRIMARY KEY,
                        vehicle_id INTEGER NOT NULL,
                        reading NUMERIC(12, 2) NOT NULL,
                        recorded_at DATETIME NOT NULL,
                        source VARCHAR(30) NOT NULL,
                        evidence_path VARCHAR(255),
                        notes VARCHAR(255),
                        created_by_user_id INTEGER NOT NULL,
                        created_at DATETIME NOT NULL
                    )
                    """
                )
            )
            db.session.commit()

            ensure_runtime_schema()

            columns = {column["name"] for column in inspect(db.engine).get_columns("hourmeter_readings")}
            self.assertTrue(
                {
                    "meter_type",
                    "previous_reading",
                    "difference_hours",
                    "validation_status",
                    "exception_justification",
                    "cancelled_at",
                    "cancelled_by_user_id",
                    "cancellation_reason",
                    "replacement_reading_id",
                }.issubset(columns)
            )


if __name__ == "__main__":
    unittest.main()
