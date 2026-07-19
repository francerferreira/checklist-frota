from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_portuary_inventory_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import EquipmentProfile, Vehicle
from app.services.inventory_import_service import read_portuary_csv, replace_portuary_inventory


class PortuaryInventoryImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.csv_path = Path(tempfile.gettempdir()) / "checklist_frota_portuary_inventory_test.csv"
        with cls.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["Tipo", "Equipamento", "Modelo", "Numero_Serie", "Ano", "Status"])
            writer.writeheader()
            writer.writerows(
                [
                    {"Tipo": "LBS", "Equipamento": "LBS01", "Modelo": "600", "Numero_Serie": "141579", "Ano": "2017", "Status": "Ativo"},
                    {"Tipo": "RTG", "Equipamento": "RTG01", "Modelo": "", "Numero_Serie": "", "Ano": "", "Status": "Ativo"},
                    {"Tipo": "SPREADER", "Equipamento": "SPREADER 01", "Modelo": "", "Numero_Serie": "34608", "Ano": "2022", "Status": "Ativo"},
                ]
            )

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        for path in (DB_PATH, cls.csv_path):
            if path.exists():
                path.unlink()

    def test_reads_three_modules(self):
        rows = read_portuary_csv(self.csv_path)
        self.assertEqual([row["tipo"] for row in rows], ["lbs", "rtg", "spreader"])

    def test_replaces_active_inventory_and_creates_profiles(self):
        with self.app.app_context():
            legacy = Vehicle(placa="S/PLACA", modelo="LEGADO", frota="LEGADO 01", tipo="carreta", ativo=True, status="ON")
            db.session.add(legacy)
            db.session.commit()

            result = replace_portuary_inventory(self.csv_path)
            self.assertEqual(result["total_csv"], 3)
            self.assertEqual(result["por_modulo"], {"LBS": 1, "RTG": 1, "SPREADER": 1})
            self.assertGreaterEqual(result["retirados_sem_apagar_historico"], 1)
            active = Vehicle.query.filter_by(ativo=True).all()
            self.assertEqual({vehicle.frota for vehicle in active}, {"LBS01", "RTG01", "SPREADER 01"})
            self.assertFalse(Vehicle.query.filter_by(frota="LEGADO 01").one().ativo)
            self.assertGreaterEqual(EquipmentProfile.query.count(), 4)
            self.assertEqual(
                EquipmentProfile.query.filter_by(vehicle_id=Vehicle.query.filter_by(frota="SPREADER 01").one().id).one().serial_number,
                "34608",
            )


if __name__ == "__main__":
    unittest.main()
