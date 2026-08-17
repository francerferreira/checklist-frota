from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class NotificationsMigrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent(self):
        path = Path(tempfile.gettempdir()) / "checklist_frota_notifications_migration_test.db"
        if path.exists():
            path.unlink()
        engine = sa.create_engine(f"sqlite:///{path}")
        metadata = sa.MetaData()
        sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
        metadata.create_all(engine)
        spec = importlib.util.spec_from_file_location(
            "notifications_migration", ROOT / "migrations" / "versions" / "20260817_0018_notifications_center.py"
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()
            self.assertIn("notifications", sa.inspect(connection).get_table_names())
            self.assertEqual(
                {column["name"] for column in sa.inspect(connection).get_columns("notifications")},
                {"id", "user_id", "title", "message", "priority", "origin", "entity_type", "entity_id", "created_at", "read_at", "expires_at"},
            )
        engine.dispose()
        if path.exists():
            path.unlink()


class NotificationsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = Path(tempfile.gettempdir()) / "checklist_frota_notifications_routes_test.db"
        if cls.db_path.exists():
            cls.db_path.unlink()
        os.environ["DATABASE_URL"] = f"sqlite:///{cls.db_path}"
        os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
        os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
        os.environ["INVENTORY_FILE"] = ""
        os.environ["WASH_CONTROL_FILE"] = ""
        from app import create_app
        from app.extensions import db
        from app.models import User
        from app.services.auth_service import generate_token

        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            cls.admin = User(nome="Administrador", login="notify-admin", tipo="admin", ativo=True)
            cls.admin.set_password("SenhaSegura123!")
            cls.operator = User(nome="Operador", login="notify-operator", tipo="operacional", ativo=True)
            cls.operator.set_password("SenhaSegura123!")
            db.session.add_all([cls.admin, cls.operator])
            db.session.commit()
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(cls.admin)}"}
            cls.operator_headers = {"Authorization": f"Bearer {generate_token(cls.operator)}"}

    @classmethod
    def tearDownClass(cls):
        from app.extensions import db

        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        for path in (cls.db_path, Path(f"{cls.db_path}-wal"), Path(f"{cls.db_path}-shm")):
            if path.exists():
                path.unlink()

    def test_login_creates_user_notification_and_read_flow(self):
        login = self.client.post("/login", json={"login": "notify-operator", "senha": "SenhaSegura123!"})
        self.assertEqual(login.status_code, 200, login.get_json())
        listed = self.client.get("/notifications", headers=self.operator_headers)
        self.assertEqual(listed.status_code, 200, listed.get_json())
        self.assertGreaterEqual(listed.get_json()["data"]["unread_count"], 1)
        notification_id = listed.get_json()["data"]["items"][0]["id"]
        marked = self.client.post(f"/notifications/{notification_id}/read", headers=self.operator_headers)
        self.assertEqual(marked.status_code, 200, marked.get_json())
        self.assertTrue(marked.get_json()["data"]["read"])

    def test_admin_can_create_and_operator_cannot_broadcast(self):
        denied = self.client.post(
            "/notifications",
            headers=self.operator_headers,
            json={"user_id": self.admin.id, "title": "Aviso", "message": "Teste"},
        )
        self.assertEqual(denied.status_code, 403, denied.get_json())
        created = self.client.post(
            "/notifications",
            headers=self.admin_headers,
            json={
                "user_id": self.operator.id,
                "title": "Manutenção",
                "message": "Há uma atividade pendente.",
                "priority": "WARNING",
                "origin": "MAINTENANCE",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        self.assertEqual(created.get_json()["data"][0]["priority"], "WARNING")

    def test_operator_can_mark_all_and_clear_own_history(self):
        self.client.post(
            "/notifications",
            headers=self.admin_headers,
            json={"user_id": self.operator.id, "title": "Aviso", "message": "Teste"},
        )
        marked = self.client.post("/notifications/read-all", headers=self.operator_headers)
        self.assertEqual(marked.status_code, 200, marked.get_json())
        self.assertEqual(marked.get_json()["data"]["unread_count"], 0)
        cleared = self.client.delete("/notifications", headers=self.operator_headers)
        self.assertEqual(cleared.status_code, 200, cleared.get_json())
        self.assertGreaterEqual(cleared.get_json()["data"]["deleted"], 1)
        from app.models import AuditLog

        with self.app.app_context():
            self.assertTrue(AuditLog.query.filter_by(entity_type="NOTIFICATION", action="DELETE").count() >= 1)

    def test_business_change_creates_automatic_notification_for_other_active_users(self):
        created = self.client.post(
            "/recursos",
            headers=self.admin_headers,
            json={
                "code": "AUTO-NOTIFY-001",
                "name": "Recurso de teste",
                "resource_type": "FERRAMENTA",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())

        listed = self.client.get("/notifications", headers=self.operator_headers)
        self.assertEqual(listed.status_code, 200, listed.get_json())
        automatic = [
            item for item in listed.get_json()["data"]["items"]
            if item["entity_type"] == "MAINTENANCE_RESOURCE"
        ]
        self.assertTrue(automatic)
        self.assertEqual(automatic[0]["origin"], "MANUTENÇÃO")
        self.assertIn("Registro aberto", automatic[0]["title"])

    def test_manual_business_event_also_creates_notification(self):
        from flask import g
        from app.extensions import db
        from app.services.audit_service import record_event

        with self.app.test_request_context("/"):
            g.current_user = self.admin
            record_event(
                user_id=self.admin.id,
                entity_type="WAREHOUSE_TRANSFER",
                entity_id=77,
                action="TRANSFER_TO_MMP",
            )
            db.session.commit()

        listed = self.client.get("/notifications", headers=self.operator_headers)
        self.assertEqual(listed.status_code, 200, listed.get_json())
        automatic = [
            item for item in listed.get_json()["data"]["items"]
            if item["entity_type"] == "WAREHOUSE_TRANSFER" and item["entity_id"] == 77
        ]
        self.assertTrue(automatic)
        self.assertEqual(automatic[0]["origin"], "ESTOQUE MMP")


if __name__ == "__main__":
    unittest.main()
