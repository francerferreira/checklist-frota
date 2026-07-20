from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services import seed_service


class PortuarySeedServiceTests(unittest.TestCase):
    def test_portuary_mode_does_not_seed_legacy_checklist_catalog(self):
        app = Flask(__name__)
        app.config["PORTUARY_ONLY_MODE"] = True

        with app.app_context(), \
            patch("app.services.seed_service._seed_initial_admin"), \
            patch("app.services.seed_service.db.session.commit"), \
            patch("app.services.seed_service.seed_equipment_structure"), \
            patch("app.services.seed_service.seed_checklist_catalog_items") as seed_catalog, \
            patch("app.services.seed_service.Vehicle.query") as vehicle_query, \
            patch("app.services.seed_service.seed_operational_states"):
            vehicle_query.count.return_value = 1

            seed_service.seed_reference_data()

        seed_catalog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
