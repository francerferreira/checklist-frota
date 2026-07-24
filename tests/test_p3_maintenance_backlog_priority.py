from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_p3_backlog_priority_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import MaintenanceSchedule, MaintenanceScheduleItem, MaintenanceWorkOrder, User, Vehicle
from app.services.auth_service import generate_token


class P3MaintenanceBacklogPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            if not admin:
                admin = User(nome="Administrador P3", login="admin", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
                db.session.flush()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG BACKLOG", tipo="rtg", ativo=True)
            db.session.add(vehicle)
            db.session.flush()
            for index in range(6):
                scheduled_date = date.today() - timedelta(days=6 - index)
                schedule = MaintenanceSchedule(
                    source_type="ATIVIDADE",
                    source_key=f"P3-BACKLOG-{index}",
                    title=f"Backlog P3 {index}",
                    status="PROGRAMADA",
                    start_date=scheduled_date,
                    end_date=scheduled_date,
                    daily_capacity=1,
                    created_by_user_id=admin.id,
                )
                db.session.add(schedule)
                db.session.flush()
                item = MaintenanceScheduleItem(
                    schedule_id=schedule.id,
                    vehicle_id=vehicle.id,
                    scheduled_date=scheduled_date,
                    status="PROGRAMADO",
                )
                db.session.add(item)
                db.session.flush()
                db.session.add(MaintenanceWorkOrder(
                    order_number=f"OS-P3-{index:02d}",
                    schedule_id=schedule.id,
                    schedule_item_id=item.id,
                    vehicle_id=vehicle.id,
                    title=f"Backlog P3 {index}",
                    status="ABERTA",
                    scheduled_date=scheduled_date,
                    created_at=datetime.combine(scheduled_date, datetime.min.time()),
                ))
            db.session.commit()
            cls.headers = {"Authorization": f"Bearer {generate_token(admin)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_overview_prioritizes_only_the_five_oldest_open_work_orders(self):
        response = self.client.get(
            f"/manutencao/visao?ano={date.today().year}&mes={date.today().month}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        backlog = response.get_json()["data"]["backlog_prioritario"]
        rows = backlog["os_mais_antigas"]
        self.assertEqual(len(rows), 5)
        self.assertEqual([row["order_number"] for row in rows], ["OS-P3-00", "OS-P3-01", "OS-P3-02", "OS-P3-03", "OS-P3-04"])
        self.assertGreater(rows[0]["age_days"], rows[-1]["age_days"])
        self.assertEqual(rows[0]["reference_type"], "DATA_PROGRAMADA")


if __name__ == "__main__":
    unittest.main()
