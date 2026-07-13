from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_technical_inspections_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import (
    EquipmentFamily, EquipmentProfile, InspectionExecution, InspectionExecutionItem,
    InspectionTemplate, InspectionTemplateItem, User, Vehicle,
    MechanicNonConformity,
)
from app.services.auth_service import generate_token


class TechnicalInspectionRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").one()
            cls.headers = {"Authorization": f"Bearer {generate_token(admin)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def setUp(self):
        with self.app.app_context():
            InspectionExecutionItem.query.delete()
            InspectionExecution.query.delete()
            InspectionTemplateItem.query.delete()
            InspectionTemplate.query.delete()
            MechanicNonConformity.query.delete()
            EquipmentProfile.query.delete()
            Vehicle.query.delete()
            family = EquipmentFamily.query.filter_by(code="rtg").one()
            vehicle = Vehicle(placa="", modelo="RTG", frota="RTG FASE 3", tipo="rtg", ativo=True)
            db.session.add(vehicle)
            db.session.flush()
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id))
            db.session.commit()
            self.family_id = family.id
            self.vehicle_id = vehicle.id

    def _create_and_publish(self):
        response = self.client.post("/inspecoes-tecnicas/modelos", headers=self.headers, json={
            "family_id": self.family_id, "code": "DIARIA", "name": "Inspecao diaria RTG",
            "items": [
                {"label": "Freio de servico", "category": "Seguranca", "response_type": "STATUS"},
                {"label": "Pressao", "category": "Motor", "response_type": "NUMERO", "unit": "bar", "minimum_value": 5, "maximum_value": 10},
            ],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        template = response.get_json()["data"]
        published = self.client.post(
            f"/inspecoes-tecnicas/modelos/{template['id']}/publicar", headers=self.headers,
        )
        self.assertEqual(published.status_code, 200, published.get_json())
        return published.get_json()["data"]

    def test_published_template_is_selected_by_equipment_family(self):
        template = self._create_and_publish()
        response = self.client.get(
            f"/inspecoes-tecnicas/modelos?vehicle_id={self.vehicle_id}", headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()["data"]
        self.assertEqual([row["id"] for row in rows], [template["id"]])
        self.assertEqual(rows[0]["family"]["code"], "rtg")

    def test_published_template_is_immutable_and_new_version_is_draft(self):
        template = self._create_and_publish()
        blocked = self.client.put(
            f"/inspecoes-tecnicas/modelos/{template['id']}", headers=self.headers,
            json={"name": "Alterado"},
        )
        self.assertEqual(blocked.status_code, 400, blocked.get_json())
        cloned = self.client.post(
            f"/inspecoes-tecnicas/modelos/{template['id']}/nova-versao", headers=self.headers,
        )
        self.assertEqual(cloned.status_code, 201, cloned.get_json())
        self.assertEqual(cloned.get_json()["data"]["version"], 2)
        self.assertEqual(cloned.get_json()["data"]["status"], "RASCUNHO")

    def test_execution_requires_nc_evidence_and_preserves_template_version(self):
        template = self._create_and_publish()
        status_item, number_item = template["items"]
        invalid = self.client.post("/inspecoes-tecnicas/execucoes", headers=self.headers, json={
            "template_id": template["id"], "vehicle_id": self.vehicle_id,
            "items": [
                {"template_item_id": status_item["id"], "status": "NC", "observation": "Vazamento"},
                {"template_item_id": number_item["id"], "value_number": 7},
            ],
        })
        self.assertEqual(invalid.status_code, 400, invalid.get_json())
        valid = self.client.post("/inspecoes-tecnicas/execucoes", headers=self.headers, json={
            "template_id": template["id"], "vehicle_id": self.vehicle_id,
            "items": [
                {"template_item_id": status_item["id"], "status": "NC", "observation": "Vazamento", "evidence_path": "/uploads/fase3.jpg"},
                {"template_item_id": number_item["id"], "value_number": 7},
            ],
        })
        self.assertEqual(valid.status_code, 201, valid.get_json())
        data = valid.get_json()["data"]
        self.assertEqual(data["result"], "NAO_CONFORME")
        self.assertEqual(data["template_version"], 1)
        generated = next(item for item in data["items"] if item["status"] == "NC")
        self.assertIsNotNone(generated["generated_non_conformity_id"])
        with self.app.app_context():
            nc = db.session.get(MechanicNonConformity, generated["generated_non_conformity_id"])
            self.assertIn("INSPECAO_TECNICA", nc.observacao)


if __name__ == "__main__":
    unittest.main()
