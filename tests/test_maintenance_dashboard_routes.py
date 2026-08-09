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

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_maintenance_dashboard_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import (
    EquipmentFamily,
    EquipmentOperationalState,
    EquipmentProfile,
    EquipmentStatusEvent,
    MaintenanceSchedule,
    MaintenanceScheduleItem,
    MaintenanceWorkOrder,
    PreventivePlan,
    User,
    Vehicle,
    WorkOrderExecution,
)
from app.services.auth_service import generate_token
from app.utils.timezone import now_manaus_naive, today_manaus


class MaintenanceDashboardRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            if not admin:
                admin = User(nome="Administrador Dashboard", login="admin", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
                db.session.flush()
            mechanic = User(nome="Mecanico Dashboard", login="mecanico_dashboard", tipo="mecanico", ativo=True)
            mechanic.set_password("teste123")
            db.session.add(mechanic)
            db.session.commit()
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.mechanic_headers = {"Authorization": f"Bearer {generate_token(mechanic)}"}
            cls.admin_id = admin.id
            cls.mechanic_id = mechanic.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def setUp(self):
        with self.app.app_context():
            WorkOrderExecution.query.delete()
            MaintenanceWorkOrder.query.delete()
            MaintenanceScheduleItem.query.delete()
            MaintenanceSchedule.query.delete()
            PreventivePlan.query.delete()
            EquipmentStatusEvent.query.delete()
            EquipmentOperationalState.query.delete()
            EquipmentProfile.query.delete()
            Vehicle.query.delete()
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG DASH 01", tipo="rtg", ativo=True)
            db.session.add(vehicle)
            db.session.flush()
            self.vehicle_id = vehicle.id
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id, criticality="CRITICA"))
            stopped_at = now_manaus_naive() - timedelta(days=2)
            db.session.add(
                EquipmentOperationalState(
                    vehicle_id=vehicle.id,
                    operational_status="INDISPONIVEL",
                    status_updated_at=stopped_at,
                    status_reason="Falha de teste",
                )
            )
            db.session.add(
                EquipmentStatusEvent(
                    vehicle_id=vehicle.id,
                    status="INDISPONIVEL",
                    reason="Falha de teste",
                    source="MANUAL",
                    started_at=stopped_at,
                    created_by_user_id=self.admin_id,
                )
            )
            plan = PreventivePlan(
                code="PP-DASH-01",
                vehicle_id=vehicle.id,
                title="Preventiva vencida",
                trigger_type="CALENDARIO",
                interval_days=30,
                next_due_date=today_manaus() - timedelta(days=1),
                priority="ALTA",
                estimated_duration_minutes=60,
                created_by_user_id=self.admin_id,
            )
            db.session.add(plan)
            db.session.flush()
            self._add_completed_order(vehicle.id, "DASH-001", now_manaus_naive() - timedelta(days=5))
            self._add_completed_order(vehicle.id, "DASH-002", now_manaus_naive() - timedelta(days=3))
            schedule = MaintenanceSchedule(
                source_type="PREVENTIVA",
                source_key=f"PREVENTIVA_PCM:{plan.id}:1",
                title="OS preventiva aberta",
                status="ABERTA",
                start_date=today_manaus() - timedelta(days=1),
                end_date=today_manaus() - timedelta(days=1),
                daily_capacity=1,
                created_by_user_id=self.admin_id,
            )
            db.session.add(schedule)
            db.session.flush()
            item = MaintenanceScheduleItem(
                schedule_id=schedule.id,
                vehicle_id=vehicle.id,
                status="PENDENTE",
            )
            db.session.add(item)
            db.session.flush()
            db.session.add(
                MaintenanceWorkOrder(
                    order_number="OS-DASH-ABERTA",
                    schedule_id=schedule.id,
                    schedule_item_id=item.id,
                    vehicle_id=vehicle.id,
                    opened_by_user_id=self.admin_id,
                    title="Preventiva aberta",
                    status="ABERTA",
                    scheduled_date=today_manaus() - timedelta(days=1),
                )
            )
            db.session.commit()

    def _add_completed_order(self, vehicle_id: int, sequence: str, failure_started_at):
        schedule = MaintenanceSchedule(
            source_type="ATIVIDADE",
            source_key=f"DASH:{sequence}",
            title=f"OS {sequence}",
            status="CONCLUIDA",
            start_date=failure_started_at.date(),
            end_date=failure_started_at.date(),
            daily_capacity=1,
            created_by_user_id=self.admin_id,
        )
        db.session.add(schedule)
        db.session.flush()
        released_at = failure_started_at + timedelta(hours=2)
        item = MaintenanceScheduleItem(
            schedule_id=schedule.id,
            vehicle_id=vehicle_id,
            status="INSTALADO",
            executed_by_user_id=self.admin_id,
            executed_at=released_at,
        )
        db.session.add(item)
        db.session.flush()
        order = MaintenanceWorkOrder(
            order_number=f"OS-{sequence}",
            schedule_id=schedule.id,
            schedule_item_id=item.id,
            vehicle_id=vehicle_id,
            opened_by_user_id=self.admin_id,
            title=f"OS {sequence}",
            status="CONCLUIDA",
            scheduled_date=failure_started_at.date(),
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(
            WorkOrderExecution(
                work_order_id=order.id,
                failure_started_at=failure_started_at,
                repair_started_at=failure_started_at,
                repair_completed_at=released_at,
                test_result="APROVADO",
                release_status="LIBERADO",
                released_at=released_at,
                released_by_user_id=self.admin_id,
            )
        )

    def test_summary_filters_and_critical_equipment_use_real_data(self):
        response = self.client.get("/dashboard-manutencao/resumo", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()["data"]
        self.assertEqual(payload["kpis"]["equipment_total"], 1)
        self.assertEqual(payload["kpis"]["equipment_unavailable"], 1)
        self.assertEqual(payload["kpis"]["work_orders"]["open"], 1)
        self.assertEqual(payload["kpis"]["work_orders"]["overdue"], 1)
        self.assertEqual(payload["kpis"]["preventives_due_or_overdue"], 1)
        self.assertEqual(payload["kpis"]["reliability"]["mttr_hours"], 2.0)
        self.assertEqual(payload["kpis"]["reliability"]["mtbf_hours"], 46.0)
        self.assertFalse(payload["data_availability"]["maintenance_costs"])

        availability = self.client.get("/dashboard-manutencao/disponibilidade", headers=self.admin_headers)
        self.assertEqual(availability.status_code, 200, availability.get_json())
        self.assertEqual(availability.get_json()["data"]["by_family"][0]["family_code"], "rtg")

        critical = self.client.get("/dashboard-manutencao/ativos-criticos", headers=self.admin_headers)
        self.assertEqual(critical.status_code, 200, critical.get_json())
        item = critical.get_json()["data"]["items"][0]
        self.assertIn("STATUS_OPERACIONAL", item["reasons"])
        self.assertIn("PREVENTIVA_VENCENDO_OU_VENCIDA", item["reasons"])

    def test_programmed_corrective_creates_calendar_item_and_work_order(self):
        response = self.client.post(
            "/manutencao/programacoes",
            headers=self.admin_headers,
            json={
                "source_type": "CORRETIVA_PROGRAMADA",
                "title": "Corretiva programada - troca de mangueira",
                "item_name": "Troca de mangueira",
                "vehicle_ids": [self.vehicle_id],
                "assigned_mechanic_user_id": self.mechanic_id,
                "start_date": today_manaus().isoformat(),
                "daily_capacity": 1,
                "status": "PROGRAMADA",
                "observation": "Problema: vazamento\nCausa: desgaste\nAção planejada: substituir mangueira",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        schedule = response.get_json()["data"]
        self.assertEqual(schedule["source_type"], "ATIVIDADE")
        self.assertEqual(schedule["source_origin_type"], "CORRETIVA_PROGRAMADA")
        self.assertEqual(schedule["itens"][0]["status"], "PROGRAMADO")
        self.assertEqual(schedule["itens"][0]["observation"], schedule["observation"])
        self.assertIsNotNone(schedule["itens"][0]["work_order"])

    def test_dashboard_requires_management_access_and_valid_filters(self):
        unauthenticated = self.client.get("/dashboard-manutencao/resumo")
        self.assertEqual(unauthenticated.status_code, 401, unauthenticated.get_json())
        forbidden = self.client.get("/dashboard-manutencao/resumo", headers=self.mechanic_headers)
        self.assertEqual(forbidden.status_code, 403, forbidden.get_json())
        invalid_date = self.client.get(
            "/dashboard-manutencao/resumo?data_inicial=invalida",
            headers=self.admin_headers,
        )
        self.assertEqual(invalid_date.status_code, 400, invalid_date.get_json())
        invalid_page = self.client.get(
            "/dashboard-manutencao/ordens?tamanho_pagina=101",
            headers=self.admin_headers,
        )
        self.assertEqual(invalid_page.status_code, 400, invalid_page.get_json())

    def test_charts_use_real_operational_records_and_short_cache(self):
        charts = self.client.get("/dashboard-manutencao/graficos", headers=self.admin_headers)
        self.assertEqual(charts.status_code, 200, charts.get_json())
        payload = charts.get_json()["data"]
        self.assertEqual(payload["availability_by_family"][0]["family_code"], "rtg")
        self.assertEqual(payload["operational_status"], [{"status": "INDISPONIVEL", "total": 1}])
        self.assertIn({"status": "ABERTA", "total": 1}, payload["work_orders_by_status"])
        self.assertIn({"status": "CONCLUIDA", "total": 2}, payload["work_orders_by_status"])
        self.assertEqual(payload["preventives_by_status"], [{"status": "VENCIDA", "total": 1}])
        self.assertEqual(payload["unavailability_reasons"], [{"reason": "Falha de teste", "total": 1}])
        self.assertFalse(payload["performance"]["cached"])
        self.assertGreaterEqual(payload["performance"]["query_duration_ms"], 0)

        cached = self.client.get("/dashboard-manutencao/graficos", headers=self.admin_headers)
        self.assertEqual(cached.status_code, 200, cached.get_json())
        self.assertTrue(cached.get_json()["data"]["performance"]["cached"])

    def test_filter_options_and_work_order_pagination(self):
        filters = self.client.get("/dashboard-manutencao/filtros", headers=self.admin_headers)
        self.assertEqual(filters.status_code, 200, filters.get_json())
        self.assertIn("rtg", [row["code"] for row in filters.get_json()["data"]["families"]])

        orders = self.client.get(
            "/dashboard-manutencao/ordens?pagina=1&tamanho_pagina=2",
            headers=self.admin_headers,
        )
        self.assertEqual(orders.status_code, 200, orders.get_json())
        self.assertEqual(orders.get_json()["data"]["total"], 3)
        self.assertEqual(len(orders.get_json()["data"]["items"]), 2)


if __name__ == "__main__":
    unittest.main()
