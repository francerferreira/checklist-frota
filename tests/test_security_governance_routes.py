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
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_security_governance_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""
os.environ["CORS_STRICT_MODE"] = "true"
os.environ["CORS_ALLOWED_ORIGINS"] = "https://web-seguro.example"
os.environ["INITIAL_ADMIN_LOGIN"] = "admin"
os.environ["INITIAL_ADMIN_PASSWORD"] = "SenhaDeTesteForte123!"

from app import create_app
from app.extensions import db
from app.models import User
from app.services.auth_service import _serializer


class SecurityGovernanceRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            cls.admin = User.query.filter_by(login="admin").one()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_health_checks_database_and_audit_runtime(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["database"], "ok")
        self.assertIn("audit", payload)
        self.assertIn("healthy", payload["audit"])

    def test_new_logout_revokes_only_the_current_session(self):
        login = self.client.post("/login", json={"login": "admin", "senha": "SenhaDeTesteForte123!"})
        self.assertEqual(login.status_code, 200, login.get_json())
        token = login.get_json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.get("/admin/audit-health", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/admin/audit-health", headers=headers).status_code, 401)

        with self.app.app_context():
            legacy_token = _serializer().dumps({"user_id": self.admin.id, "tipo": self.admin.tipo})
        legacy_headers = {"Authorization": f"Bearer {legacy_token}"}
        self.assertEqual(self.client.get("/admin/audit-health", headers=legacy_headers).status_code, 200)

    def test_cors_allows_only_the_configured_web_origin(self):
        allowed = self.client.get("/health", headers={"Origin": "https://web-seguro.example"})
        blocked = self.client.get("/health", headers={"Origin": "https://example-attacker.invalid"})
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Origin"), "https://web-seguro.example")
        self.assertIsNone(blocked.headers.get("Access-Control-Allow-Origin"))


if __name__ == "__main__":
    unittest.main()
