from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_intelligence_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""
os.environ["AUTOMATION_JOB_TOKEN"] = "fase8-job-test"

from app import create_app
from app.extensions import db
from app.models import (
    EmergencyEvent,
    AuditLog,
    EquipmentFamily,
    EquipmentProfile,
    MaintenanceSchedule,
    MaintenanceScheduleItem,
    MaintenanceWorkOrder,
    Material,
    PreventivePlan,
    User,
    Vehicle,
    WorkOrderExecution,
)
from app.services.auth_service import generate_token
from app.utils.timezone import now_manaus_naive, today_manaus


class MaintenanceIntelligenceRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            if not admin:
                admin = User(nome="Administrador Teste", login="admin", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
                db.session.flush()
            mechanic = User(nome="Mecanico Inteligencia", login="mecanico_f7", tipo="mecanico", ativo=True)
            mechanic.set_password("teste123")
            db.session.add(mechanic)
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG FASE 7", tipo="rtg", ativo=True)
            db.session.add(vehicle)
            db.session.flush()
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id))
            cls._create_completed_work_order(vehicle.id, admin.id, "F7-001", hours_until_next_failure=48, first=True)
            cls._create_completed_work_order(vehicle.id, admin.id, "F7-002", hours_until_next_failure=48, first=False)
            db.session.add(Material(referencia="MAT-F7", descricao="Material Fase 7", quantidade_estoque=0, estoque_minimo=2, ativo=True))
            db.session.add(
                PreventivePlan(
                    code="PP-F7", vehicle_id=vehicle.id, title="Preventiva vencida", trigger_type="CALENDARIO",
                    interval_days=30, next_due_date=today_manaus() - timedelta(days=2), priority="ALTA",
                    estimated_duration_minutes=60, created_by_user_id=admin.id,
                )
            )
            db.session.add(
                EmergencyEvent(
                    event_number="EMG-F7", vehicle_id=vehicle.id, severity="CRITICA", status="ABERTA",
                    equipment_stopped=True, title="Falha critica", description="Falha aberta para alerta.",
                    reported_by_user_id=admin.id,
                )
            )
            db.session.commit()
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.mechanic_headers = {"Authorization": f"Bearer {generate_token(mechanic)}"}

    @classmethod
    def _create_completed_work_order(cls, vehicle_id, user_id, sequence, hours_until_next_failure, *, first):
        base = now_manaus_naive() - timedelta(days=8)
        if not first:
            base = base + timedelta(hours=12 + hours_until_next_failure)
        repair_started = base + timedelta(hours=1)
        released_at = repair_started + timedelta(hours=11 if first else 4)
        schedule = MaintenanceSchedule(
            source_type="ATIVIDADE", source_key=f"INTEL:{sequence}", title=f"OS {sequence}", item_name="Falha",
            status="CONCLUIDA", start_date=base.date(), end_date=base.date(), daily_capacity=1,
            created_by_user_id=user_id,
        )
        db.session.add(schedule)
        db.session.flush()
        item = MaintenanceScheduleItem(schedule_id=schedule.id, vehicle_id=vehicle_id, status="INSTALADO", executed_by_user_id=user_id, executed_at=released_at)
        db.session.add(item)
        db.session.flush()
        order = MaintenanceWorkOrder(
            order_number=f"OS-{sequence}", schedule_id=schedule.id, schedule_item_id=item.id, vehicle_id=vehicle_id,
            opened_by_user_id=user_id, title=f"OS {sequence}", status="CONCLUIDA", scheduled_date=base.date(),
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(
            WorkOrderExecution(
                work_order_id=order.id, failure_started_at=base, repair_started_at=repair_started,
                repair_completed_at=released_at, test_result="APROVADO", release_status="LIBERADO",
                released_at=released_at, released_by_user_id=user_id,
            )
        )

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_executive_metrics_and_automations_are_auditable(self):
        dashboard = self.client.get("/relatorios/dashboard", headers=self.admin_headers)
        self.assertEqual(dashboard.status_code, 200, dashboard.get_json())
        intelligence = dashboard.get_json()["data"]["manutencao_portuaria"]
        self.assertEqual(intelligence["confiabilidade"]["mtbf_horas"], 48.0)
        self.assertEqual(intelligence["confiabilidade"]["mttr_horas"], 7.5)
        self.assertEqual(intelligence["backlog"]["total"], 0)
        executive = self.client.get("/relatorios/manutencao-executivo", headers=self.admin_headers)
        self.assertEqual(executive.status_code, 200, executive.get_json())

        forbidden = self.client.post("/inteligencia/automacoes/avaliar", headers=self.mechanic_headers)
        self.assertEqual(forbidden.status_code, 403, forbidden.get_json())
        evaluated = self.client.post("/inteligencia/automacoes/avaliar", headers=self.admin_headers)
        self.assertEqual(evaluated.status_code, 200, evaluated.get_json())
        self.assertEqual(evaluated.get_json()["data"]["novos_alertas"], 3)
        alerts = self.client.get("/inteligencia/automacoes", headers=self.admin_headers).get_json()["data"]
        self.assertEqual(len(alerts), 3)
        acknowledged = self.client.put(f"/inteligencia/automacoes/{alerts[0]['id']}/reconhecer", headers=self.admin_headers)
        self.assertEqual(acknowledged.status_code, 200, acknowledged.get_json())
        self.assertEqual(acknowledged.get_json()["data"]["status"], "RECONHECIDO")
        with self.app.app_context():
            self.assertGreaterEqual(AuditLog.query.filter_by(entity_type="AUTOMATION_EXECUTION").count(), 4)

    def test_scheduled_automation_requires_dedicated_token(self):
        missing = self.client.post("/inteligencia/automacoes/executar-agendada")
        self.assertEqual(missing.status_code, 401, missing.get_json())
        invalid = self.client.post(
            "/inteligencia/automacoes/executar-agendada",
            headers={"X-Automation-Token": "invalido"},
        )
        self.assertEqual(invalid.status_code, 401, invalid.get_json())
        executed = self.client.post(
            "/inteligencia/automacoes/executar-agendada",
            headers={"X-Automation-Token": "fase8-job-test"},
        )
        self.assertEqual(executed.status_code, 200, executed.get_json())
        self.assertEqual(executed.get_json()["data"]["origem"], "AGENDADA")
        with self.app.app_context():
            self.assertGreaterEqual(AuditLog.query.filter_by(action="SCHEDULED_EVALUATION").count(), 1)


if __name__ == "__main__":
    unittest.main()
