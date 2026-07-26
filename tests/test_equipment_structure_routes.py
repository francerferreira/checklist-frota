from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_equipment_structure_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import (
    AuditLog,
    EquipmentFamily,
    EquipmentLink,
    EquipmentLocationMovement,
    EquipmentProfile,
    EquipmentStatusEvent,
    OperationalLocation,
    User,
    Vehicle,
)
from app.services.auth_service import generate_token
from app.utils.timezone import now_manaus_naive


class EquipmentStructureRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            assert admin is not None
            cls.headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            operator = User(nome="Operador Local", login="operador_local", tipo="motorista", ativo=True)
            operator.set_password("teste123")
            db.session.add(operator)
            db.session.commit()
            cls.operator_headers = {"Authorization": f"Bearer {generate_token(operator)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        with self.app.app_context():
            EquipmentStatusEvent.query.delete()
            EquipmentLocationMovement.query.delete()
            EquipmentLink.query.delete()
            EquipmentProfile.query.delete()
            Vehicle.query.delete()
            OperationalLocation.query.delete()
            db.session.commit()

    def _family(self, code: str) -> dict:
        response = self.client.get("/equipamentos/estrutura", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        families = response.get_json()["data"]["families"]
        return next(family for family in families if family["code"] == code)

    def _create_vehicle(self, *, frota: str, family: dict, model: str, **extra) -> dict:
        payload = {
            "frota": frota,
            "tipo": family["code"],
            "family_id": family["id"],
            "placa": "",
            "modelo": model,
            "status": "ON",
            "ativo": True,
            **extra,
        }
        response = self.client.post("/veiculos", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["data"]

    def test_default_port_families_are_available_without_enabling_checklist(self):
        for code in ("rtg", "lbs", "spreader"):
            family = self._family(code)
            self.assertFalse(family["checklist_enabled"])

    def test_lbs_spreader_profile_location_and_active_link_flow(self):
        location_response = self.client.post(
            "/equipamentos/locais",
            json={
                "code": "ALFA-BERCO-04",
                "name": "Berco 04 Alfandegado",
                "location_type": "BERCO",
            },
            headers=self.headers,
        )
        self.assertEqual(location_response.status_code, 201, location_response.get_json())
        location = location_response.get_json()["data"]

        lbs_family = self._family("lbs")
        spreader_family = self._family("spreader")
        lbs = self._create_vehicle(
            frota="LBS 13",
            family=lbs_family,
            model="LBS 600",
            serial_number="141582",
            manufacturer="Liebherr",
            criticality="CRITICA",
            operational_location_id=location["id"],
        )
        spreader = self._create_vehicle(
            frota="SPREADER 03",
            family=spreader_family,
            model="EH5U",
            serial_number="34610",
            capacity="41 TON",
            criticality="ALTA",
            parent_equipment_id=lbs["id"],
            link_type="TITULAR",
        )

        self.assertEqual(lbs["family"]["code"], "lbs")
        self.assertEqual(lbs["operational_location"]["id"], location["id"])
        self.assertEqual(lbs["criticality"], "CRITICA")
        self.assertFalse(lbs["checklist_available"])
        self.assertEqual(spreader["active_link"]["parent_vehicle_id"], lbs["id"])
        self.assertEqual(spreader["active_link"]["link_type"], "TITULAR")

        response = self.client.get("/veiculos?tipo=spreader&ativos=true", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()["data"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["serial_number"], "34610")
        self.assertEqual(rows[0]["active_link"]["parent_equipment"]["frota"], "LBS 13")

    def test_link_rejects_non_lbs_parent(self):
        rtg = self._create_vehicle(
            frota="RTG 01",
            family=self._family("rtg"),
            model="RTG",
        )
        response = self.client.post(
            "/veiculos",
            json={
                "frota": "SPREADER 01",
                "tipo": "spreader",
                "family_id": self._family("spreader")["id"],
                "modelo": "EH5U",
                "parent_equipment_id": rtg["id"],
                "link_type": "RESERVA",
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertIn("Spreader", response.get_json()["error"])

    def test_spreader_daily_history_combines_status_and_link_at_the_event_time(self):
        location_response = self.client.post(
            "/equipamentos/locais",
            json={"code": "BERCO-02", "name": "Berco 02", "location_type": "BERCO"},
            headers=self.headers,
        )
        self.assertEqual(location_response.status_code, 201, location_response.get_json())
        location = location_response.get_json()["data"]
        lbs = self._create_vehicle(
            frota="LBS 03",
            family=self._family("lbs"),
            model="LBS 600",
            serial_number="141714",
            operational_location_id=location["id"],
        )
        spreader = self._create_vehicle(
            frota="SPREADER 02",
            family=self._family("spreader"),
            model="EH5U",
            serial_number="34960",
            parent_equipment_id=lbs["id"],
            link_type="TITULAR",
        )
        event_at = now_manaus_naive() + timedelta(minutes=1)
        with self.app.app_context():
            admin = User.query.filter_by(login="admin").first()
            db.session.add(
                EquipmentStatusEvent(
                    vehicle_id=spreader["id"],
                    status="INDISPONIVEL",
                    reason="Inspeção apontou falha hidráulica",
                    observation="Aguardando avaliação da manutenção.",
                    evidence_path="/uploads/spreader-02.jpg",
                    started_at=event_at,
                    created_by_user_id=admin.id,
                )
            )
            db.session.commit()

        response = self.client.get(
            "/equipamentos/spreaders/historico",
            query_string={"data_inicial": event_at.date().isoformat(), "data_final": event_at.date().isoformat()},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()["data"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["spreader"]["frota"], "SPREADER 02")
        self.assertEqual(rows[0]["lbs"]["frota"], "LBS 03")
        self.assertEqual(rows[0]["lbs"]["location"], "Berco 02")
        self.assertEqual(rows[0]["link_type"], "TITULAR")
        self.assertEqual(rows[0]["evidence_path"], "/uploads/spreader-02.jpg")

    def test_location_movement_updates_current_location_and_keeps_audit_history(self):
        origin_response = self.client.post(
            "/equipamentos/locais",
            json={"code": "PATIO-ATR-01", "name": "Patio ATR 01", "location_type": "PATIO"},
            headers=self.headers,
        )
        destination_response = self.client.post(
            "/equipamentos/locais",
            json={"code": "PATIO-ALFA-04", "name": "Patio Alfandegado 04", "location_type": "PATIO"},
            headers=self.headers,
        )
        self.assertEqual(origin_response.status_code, 201, origin_response.get_json())
        self.assertEqual(destination_response.status_code, 201, destination_response.get_json())
        origin = origin_response.get_json()["data"]
        destination = destination_response.get_json()["data"]
        vehicle = self._create_vehicle(
            frota="RTG MOV 01",
            family=self._family("rtg"),
            model="RTG",
            operational_location_id=origin["id"],
        )

        forbidden = self.client.post(
            f"/equipamentos/{vehicle['id']}/movimentos-localizacao",
            json={"to_location_id": destination["id"], "reason": "Mudanca de patio"},
            headers=self.operator_headers,
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.get_json())

        moved = self.client.post(
            f"/equipamentos/{vehicle['id']}/movimentos-localizacao",
            json={
                "to_location_id": destination["id"],
                "reason": "Mudanca de patio operacional",
                "notes": "Movimento controlado da Fase 3A",
            },
            headers=self.headers,
        )
        self.assertEqual(moved.status_code, 201, moved.get_json())
        movement = moved.get_json()["data"]
        self.assertEqual(movement["from_location_id"], origin["id"])
        self.assertEqual(movement["to_location_id"], destination["id"])
        self.assertEqual(movement["source"], "MANUAL")

        history = self.client.get(
            f"/equipamentos/{vehicle['id']}/movimentos-localizacao",
            headers=self.operator_headers,
        )
        self.assertEqual(history.status_code, 200, history.get_json())
        data = history.get_json()["data"]
        self.assertEqual(data["current_location"]["id"], destination["id"])
        self.assertEqual(len(data["movements"]), 1)

        duplicate = self.client.post(
            f"/equipamentos/{vehicle['id']}/movimentos-localizacao",
            json={"to_location_id": destination["id"], "reason": "Mesmo local"},
            headers=self.headers,
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.get_json())

        with self.app.app_context():
            current = db.session.get(Vehicle, vehicle["id"])
            self.assertEqual(current.equipment_profile.operational_location_id, destination["id"])
            self.assertEqual(current.local, "Patio Alfandegado 04")
            self.assertEqual(
                AuditLog.query.filter_by(
                    entity_type="EQUIPMENT_LOCATION_MOVEMENT",
                    entity_id=movement["id"],
                    action="LOCATION_MOVED",
                ).count(),
                1,
            )


if __name__ == "__main__":
    unittest.main()
