from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_maintenance_governance_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import (
    AuditLog,
    EquipmentFamily,
    EquipmentProfile,
    MaintenanceSchedule,
    MaintenanceScheduleItem,
    MaintenanceWorkOrder,
    MaintenanceWorkOrderCost,
    SystemSetting,
    User,
    Vehicle,
)
from app.services.auth_service import generate_token


class MaintenanceGovernanceRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            if not admin:
                admin = User(nome="Administrador", login="admin", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
            mechanic = User(nome="Mecanico", login="mecanico_governanca", tipo="mecanico", ativo=True)
            mechanic.set_password("teste123")
            db.session.add(mechanic)
            db.session.commit()
            cls.admin_id = admin.id
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.mechanic_headers = {"Authorization": f"Bearer {generate_token(mechanic)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def setUp(self):
        with self.app.app_context():
            MaintenanceWorkOrderCost.query.delete()
            MaintenanceWorkOrder.query.delete()
            MaintenanceScheduleItem.query.delete()
            MaintenanceSchedule.query.delete()
            AuditLog.query.delete()
            SystemSetting.query.filter_by(key="maintenance_governance_targets").delete()
            EquipmentProfile.query.delete()
            Vehicle.query.delete()
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG GOV 01", tipo="rtg", ativo=True)
            db.session.add(vehicle)
            db.session.flush()
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id, criticality="ALTA"))
            schedule = MaintenanceSchedule(
                source_type="PREVENTIVA",
                source_key="GOV-001",
                title="Governanca de OS",
                status="ABERTA",
                daily_capacity=1,
                created_by_user_id=self.admin_id,
            )
            db.session.add(schedule)
            db.session.flush()
            item = MaintenanceScheduleItem(
                schedule_id=schedule.id,
                vehicle_id=vehicle.id,
                scheduled_date=date.today(),
                status="PENDENTE",
            )
            db.session.add(item)
            db.session.flush()
            order = MaintenanceWorkOrder(
                order_number="OS-GOV-001",
                schedule_id=schedule.id,
                schedule_item_id=item.id,
                vehicle_id=vehicle.id,
                opened_by_user_id=self.admin_id,
                title="OS de governanca",
                status="ABERTA",
            )
            db.session.add(order)
            db.session.commit()
            self.work_order_id = order.id
            self.item_id = item.id

    def test_management_records_classification_and_costs_with_audit(self):
        classification = self.client.put(
            f"/manutencao/os/{self.work_order_id}/classificacao",
            headers=self.admin_headers,
            json={"failure_cause": "Desgaste", "affected_component": "Spreader", "work_shift": "B"},
        )
        self.assertEqual(classification.status_code, 200, classification.get_json())
        self.assertEqual(classification.get_json()["data"]["classification"]["failure_cause"], "Desgaste")

        cost = self.client.post(
            f"/manutencao/os/{self.work_order_id}/custos",
            headers=self.admin_headers,
            json={
                "category": "PECA",
                "description": "Cabo de aco",
                "supplier_name": "Fornecedor teste",
                "affected_component": "Spreader",
                "amount": "1250.50",
            },
        )
        self.assertEqual(cost.status_code, 201, cost.get_json())
        data = cost.get_json()["data"]
        self.assertEqual(data["cost_summary"]["total"], 1250.5)
        self.assertEqual(data["cost_summary"]["by_category"]["PECA"], 1250.5)
        cost_id = data["costs"][0]["id"]

        budget = self.client.put(
            f"/manutencao/os/{self.work_order_id}/orcamento",
            headers=self.admin_headers,
            json={"amount": "1000.00", "notes": "Limite aprovado para a intervenção"},
        )
        self.assertEqual(budget.status_code, 200, budget.get_json())
        budget_summary = budget.get_json()["data"]["budget_summary"]
        self.assertEqual(budget_summary["budget_amount"], 1000.0)
        self.assertEqual(budget_summary["actual_amount"], 1250.5)
        self.assertEqual(budget_summary["variance"], 250.5)

        dashboard = self.client.get("/dashboard-manutencao/resumo", headers=self.admin_headers)
        self.assertEqual(dashboard.status_code, 200, dashboard.get_json())
        availability = dashboard.get_json()["data"]["data_availability"]
        self.assertTrue(availability["maintenance_costs"])
        self.assertTrue(availability["failure_cause"])
        self.assertTrue(availability["work_shift"])

        with self.app.app_context():
            self.assertEqual(MaintenanceWorkOrderCost.query.count(), 1)
            actions = {row.action for row in AuditLog.query.all()}
            self.assertIn("GOVERNANCE_CLASSIFICATION_UPDATED", actions)
            self.assertIn("COST_RECORDED", actions)
            self.assertIn("BUDGET_UPDATED", actions)

        deleted = self.client.delete(
            f"/manutencao/os/{self.work_order_id}/custos/{cost_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        self.assertEqual(deleted.get_json()["data"]["cost_summary"]["records"], 0)

    def test_targets_have_no_fake_defaults_and_validate_limits(self):
        initial = self.client.get("/manutencao/governanca/metas", headers=self.admin_headers)
        self.assertEqual(initial.status_code, 200, initial.get_json())
        self.assertFalse(initial.get_json()["data"]["configured"])
        self.assertIsNone(initial.get_json()["data"]["targets"]["mtbf_min_hours"])

        saved = self.client.put(
            "/manutencao/governanca/metas",
            headers=self.admin_headers,
            json={"availability_min_percent": 92, "mttr_max_hours": 8, "mtbf_min_hours": 120},
        )
        self.assertEqual(saved.status_code, 200, saved.get_json())
        self.assertTrue(saved.get_json()["data"]["configured"])
        self.assertEqual(saved.get_json()["data"]["targets"]["availability_min_percent"], 92.0)
        self.assertIsNone(saved.get_json()["data"]["targets"]["preventive_compliance_min_percent"])

        invalid = self.client.put(
            "/manutencao/governanca/metas",
            headers=self.admin_headers,
            json={"availability_min_percent": 101},
        )
        self.assertEqual(invalid.status_code, 400, invalid.get_json())

    def test_mechanic_cannot_access_financial_governance(self):
        response = self.client.get(
            f"/manutencao/os/{self.work_order_id}/governanca",
            headers=self.mechanic_headers,
        )
        self.assertEqual(response.status_code, 403, response.get_json())

    def test_overview_filters_by_family_at_api_boundary(self):
        current = date.today()
        rtg = self.client.get(
            f"/manutencao/visao?ano={current.year}&mes={current.month}&familia=rtg",
            headers=self.admin_headers,
        )
        self.assertEqual(rtg.status_code, 200, rtg.get_json())
        self.assertEqual(len(rtg.get_json()["data"]["itens"]), 1)
        self.assertEqual(rtg.get_json()["data"]["itens"][0]["vehicle"]["family"]["code"], "rtg")

        lbs = self.client.get(
            f"/manutencao/visao?ano={current.year}&mes={current.month}&familia=lbs",
            headers=self.admin_headers,
        )
        self.assertEqual(lbs.status_code, 200, lbs.get_json())
        self.assertEqual(lbs.get_json()["data"]["itens"], [])

        invalid = self.client.get(
            f"/manutencao/visao?ano={current.year}&mes={current.month}&familia=rtg/bad",
            headers=self.admin_headers,
        )
        self.assertEqual(invalid.status_code, 400, invalid.get_json())

    def test_mechanic_schedule_list_is_scoped_to_assignments(self):
        mechanic = self.client.get("/manutencao/programacoes", headers=self.mechanic_headers)
        self.assertEqual(mechanic.status_code, 200, mechanic.get_json())
        self.assertEqual(mechanic.get_json()["data"], [])

        manager = self.client.get("/manutencao/programacoes", headers=self.admin_headers)
        self.assertEqual(manager.status_code, 200, manager.get_json())
        self.assertEqual(len(manager.get_json()["data"]), 1)

    def test_reprogramming_requires_reason_and_records_audit(self):
        missing_reason = self.client.put(
            f"/manutencao/itens/{self.item_id}/reprogramar",
            headers=self.admin_headers,
            json={"scheduled_date": "2026-08-01"},
        )
        self.assertEqual(missing_reason.status_code, 400, missing_reason.get_json())

        reprogrammed = self.client.put(
            f"/manutencao/itens/{self.item_id}/reprogramar",
            headers=self.admin_headers,
            json={"scheduled_date": "2026-08-01", "reason": "Janela operacional indisponível"},
        )
        self.assertEqual(reprogrammed.status_code, 200, reprogrammed.get_json())
        self.assertEqual(reprogrammed.get_json()["data"]["status"], "REPROGRAMADO")

        with self.app.app_context():
            audit = AuditLog.query.filter_by(
                entity_type="MAINTENANCE_SCHEDULE_ITEM",
                entity_id=self.item_id,
                action="REPROGRAMMED",
            ).one()
            self.assertIn("Janela operacional indisponível", audit.new_value)


if __name__ == "__main__":
    unittest.main()
