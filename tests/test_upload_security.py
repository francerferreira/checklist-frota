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

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_upload_security_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import User
from app.services.auth_service import generate_token


class UploadSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            assert admin is not None
            cls.headers = {"Authorization": f"Bearer {generate_token(admin)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def test_local_upload_download_requires_authentication(self):
        response = self.client.get("/uploads/arquivo-inexistente.jpg")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "Nao autorizado."})

    def test_supabase_upload_download_requires_authentication(self):
        response = self.client.get("/uploads/supabase/pasta/arquivo-inexistente.jpg")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "Nao autorizado."})

    def test_local_upload_download_keeps_authenticated_flow(self):
        response = self.client.get("/uploads/arquivo-inexistente.jpg", headers=self.headers)
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
