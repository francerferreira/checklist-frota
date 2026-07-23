from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_material_policy_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import User
from app.services.auth_service import generate_token


class MaterialPolicyRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User(nome="Administrador Materiais", login="admin_materiais", tipo="admin", ativo=True)
            admin.set_password("teste123")
            db.session.add(admin)
            db.session.commit()
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_material_policy_exposes_reorder_point_and_abc_class(self):
        created = self.client.post(
            "/materiais",
            headers=self.admin_headers,
            json={
                "referencia": "MAT-ABC-01",
                "descricao": "Filtro hidráulico",
                "aplicacao_tipo": "ambos",
                "quantidade_estoque": 4,
                "estoque_minimo": 2,
                "ponto_reposicao": 5,
                "classe_abc": "A",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        material = created.get_json()["data"]
        self.assertEqual(material["ponto_reposicao"], 5)
        self.assertEqual(material["classe_abc"], "A")
        self.assertTrue(material["repor"])

        updated = self.client.put(
            f"/materiais/{material['id']}",
            headers=self.admin_headers,
            json={
                "referencia": "MAT-ABC-01",
                "descricao": "Filtro hidráulico revisado",
                "aplicacao_tipo": "ambos",
                "estoque_minimo": 2,
                "ponto_reposicao": 3,
                "classe_abc": "B",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["data"]["classe_abc"], "B")
        self.assertFalse(updated.get_json()["data"]["repor"])

    def test_invalid_abc_class_is_rejected(self):
        response = self.client.post(
            "/materiais",
            headers=self.admin_headers,
            json={
                "referencia": "MAT-ABC-INVALIDO",
                "descricao": "Material inválido",
                "classe_abc": "D",
            },
        )
        self.assertEqual(response.status_code, 400, response.get_json())


if __name__ == "__main__":
    unittest.main()
