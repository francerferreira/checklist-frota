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
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_management_master_base_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import (
    EquipmentFamily,
    EquipmentProfile,
    MaintenanceSchedule,
    MaintenanceScheduleItem,
    MaintenanceWorkOrder,
    OperationalLocation,
    User,
    Vehicle,
)
from app.services.auth_service import generate_token
from app.utils.timezone import today_manaus


class ManagementMasterBaseRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            if not admin:
                admin = User(nome="Administrador Base", login="admin", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
                db.session.flush()
            mechanic = User(nome="Mecanico Base", login="mecanico_base", tipo="mecanico", ativo=True)
            mechanic.set_password("teste123")
            db.session.add(mechanic)
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            location = OperationalLocation(code="BASE-MESTRE-01", name="Patio Base Mestre", location_type="PATIO")
            db.session.add(location)
            active_vehicle = Vehicle(placa="", modelo="RTG", frota="RTG BASE 01", tipo="rtg", ativo=True)
            inactive_vehicle = Vehicle(placa="", modelo="RTG", frota="RTG BASE 02", tipo="rtg", ativo=False)
            db.session.add_all([active_vehicle, inactive_vehicle])
            db.session.flush()
            db.session.add_all(
                [
                    EquipmentProfile(vehicle_id=active_vehicle.id, family_id=family.id, operational_location_id=location.id),
                    EquipmentProfile(vehicle_id=inactive_vehicle.id, family_id=family.id, operational_location_id=location.id),
                ]
            )
            db.session.flush()
            for index, vehicle in enumerate((active_vehicle, inactive_vehicle), start=1):
                schedule = MaintenanceSchedule(
                    source_type="PREVENTIVA",
                    source_key=f"BASE:{index}",
                    title=f"Preventiva Base {index}",
                    item_name="Inspecao estrutural",
                    status="PROGRAMADA",
                    start_date=today_manaus() - timedelta(days=index),
                    end_date=today_manaus() - timedelta(days=index),
                    daily_capacity=1,
                    created_by_user_id=admin.id,
                )
                db.session.add(schedule)
                db.session.flush()
                item = MaintenanceScheduleItem(
                    schedule_id=schedule.id,
                    vehicle_id=vehicle.id,
                    scheduled_date=today_manaus() - timedelta(days=index),
                    status="PROGRAMADO",
                    assigned_mechanic_user_id=mechanic.id,
                )
                db.session.add(item)
                db.session.flush()
                db.session.add(
                    MaintenanceWorkOrder(
                        order_number=f"OS-BASE-{index}",
                        schedule_id=schedule.id,
                        schedule_item_id=item.id,
                        vehicle_id=vehicle.id,
                        assigned_mechanic_user_id=mechanic.id,
                        opened_by_user_id=admin.id,
                        title=schedule.title,
                        item_name=schedule.item_name,
                        status="PROGRAMADA",
                        scheduled_date=item.scheduled_date,
                    )
                )
            db.session.commit()
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.mechanic_headers = {"Authorization": f"Bearer {generate_token(mechanic)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_management_base_is_paginated_and_filters_active_equipment(self):
        response = self.client.get(
            "/relatorios/base-mestre?pagina=1&tamanho_pagina=1&familia=RTG&status=programada",
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()["data"]
        self.assertEqual(data["schema_version"], "pcm.base_mestre.v1")
        self.assertEqual(data["pagination"], {
            "page": 1,
            "page_size": 1,
            "total": 1,
            "total_pages": 1,
            "has_next": False,
            "has_previous": False,
        })
        row = data["items"][0]
        self.assertEqual(row["order_number"], "OS-BASE-1")
        self.assertEqual(row["vehicle"]["frota"], "RTG BASE 01")
        self.assertEqual(row["family"]["code"], "rtg")
        self.assertEqual(row["location"]["name"], "Patio Base Mestre")
        self.assertEqual(row["status"], "PROGRAMADA")

    def test_management_base_requires_management_access_and_valid_parameters(self):
        forbidden = self.client.get("/relatorios/base-mestre", headers=self.mechanic_headers)
        self.assertEqual(forbidden.status_code, 403, forbidden.get_json())

        invalid_page = self.client.get("/relatorios/base-mestre?pagina=0", headers=self.admin_headers)
        self.assertEqual(invalid_page.status_code, 400, invalid_page.get_json())

        invalid_dates = self.client.get(
            "/relatorios/base-mestre?data_inicial=2026-07-20&data_final=2026-07-01",
            headers=self.admin_headers,
        )
        self.assertEqual(invalid_dates.status_code, 400, invalid_dates.get_json())

        all_rows = self.client.get("/relatorios/base-mestre?ativos=false", headers=self.admin_headers)
        self.assertEqual(all_rows.status_code, 200, all_rows.get_json())
        self.assertEqual(all_rows.get_json()["data"]["pagination"]["total"], 2)

    def test_bi_contract_is_versioned_read_only_and_restricted_to_management(self):
        response = self.client.get("/relatorios/bi/contrato", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()["data"]
        self.assertEqual(data["schema_version"], "bi.sqlite.readonly.v1")
        self.assertEqual(data["access"]["mode"], "EXPORTACAO_CONTROLADA")
        self.assertFalse(data["access"]["database_write"])
        master = next(dataset for dataset in data["datasets"] if dataset["id"] == "pcm_base_mestre")
        self.assertEqual(master["schema_version"], "pcm.base_mestre.v1")
        self.assertIn("vehicle_frota", master["columns"])
        forbidden = self.client.get("/relatorios/bi/contrato", headers=self.mechanic_headers)
        self.assertEqual(forbidden.status_code, 403, forbidden.get_json())

    def test_management_base_exports_keep_a_typed_contract(self):
        json_export = self.client.get(
            "/relatorios/base-mestre/exportar?formato=json",
            headers=self.admin_headers,
        )
        self.assertEqual(json_export.status_code, 200, json_export.get_json())
        export_data = json_export.get_json()["data"]
        self.assertEqual(export_data["schema_version"], "pcm.base_mestre.v1")
        self.assertEqual(export_data["exported"], 1)
        self.assertIn("vehicle_frota", export_data["columns"])

        csv_export = self.client.get(
            "/relatorios/base-mestre/exportar?formato=csv",
            headers=self.admin_headers,
        )
        self.assertEqual(csv_export.status_code, 200, csv_export.get_data(as_text=True))
        self.assertIn("vehicle_frota", csv_export.get_data(as_text=True))
        self.assertIn("RTG BASE 01", csv_export.get_data(as_text=True))

        xlsx_export = self.client.get(
            "/relatorios/base-mestre/exportar?formato=xlsx",
            headers=self.admin_headers,
        )
        self.assertEqual(xlsx_export.status_code, 200, xlsx_export.status)
        self.assertTrue(xlsx_export.data.startswith(b"PK"))


if __name__ == "__main__":
    unittest.main()
