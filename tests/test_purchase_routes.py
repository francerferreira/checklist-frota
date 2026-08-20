from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_purchase_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import Material, PurchaseServiceCatalog, User
from app.services.auth_service import generate_token


class PurchaseRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            admin = User(nome="Administrador Compras", login="admin_compras", tipo="admin", ativo=True)
            admin.set_password("teste123")
            gestor = User(nome="Gestor Compras", login="gestor_compras", tipo="gestor", ativo=True)
            gestor.set_password("teste123")
            material = Material(referencia="MAT-COMPRA", descricao="Kit hidráulico", aplicacao_tipo="ambos", quantidade_estoque=0, estoque_minimo=2)
            service = PurchaseServiceCatalog(code="SERV-001", service_name="Reparo de bomba hidráulica", active=True)
            db.session.add_all([admin, gestor, material, service])
            db.session.commit()
            cls.material_id = material.id
            cls.service_id = service.id
            cls.admin_headers = {"Authorization": f"Bearer {generate_token(admin)}"}
            cls.gestor_headers = {"Authorization": f"Bearer {generate_token(gestor)}"}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def test_purchase_request_approval_partial_receipt_and_idempotency(self):
        supplier = self.client.post(
            "/compras/provedores",
            headers=self.admin_headers,
            json={"code": "PROV-001", "name": "Provedor Hidráulico", "email": "compras@example.test"},
        )
        self.assertEqual(supplier.status_code, 201, supplier.get_json())
        supplier_id = supplier.get_json()["data"]["id"]

        request = self.client.post(
            "/compras/solicitacoes",
            headers=self.gestor_headers,
            json={
                "material_id": self.material_id,
                "supplier_id": supplier_id,
                "requested_quantity": 5,
                "priority": "CRITICA",
                "expected_date": (date.today() + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(request.status_code, 201, request.get_json())
        purchase = request.get_json()["data"]

        filtered_requests = self.client.get(
            f"/compras/solicitacoes?modo=OPERACIONAL&page=1&per_page=100&q={purchase['sc_number']}&status=AGUARDANDO_PC",
            headers=self.gestor_headers,
        )
        self.assertEqual(filtered_requests.status_code, 200, filtered_requests.get_json())
        filtered_request_data = filtered_requests.get_json()["data"]
        self.assertEqual(filtered_request_data["pagination"]["total"], 1)
        self.assertEqual(filtered_request_data["items"][0]["id"], purchase["id"])

        gestor_approval = self.client.post(f"/compras/solicitacoes/{purchase['id']}/aprovar", headers=self.gestor_headers)
        self.assertEqual(gestor_approval.status_code, 403, gestor_approval.get_json())
        approved = self.client.post(f"/compras/solicitacoes/{purchase['id']}/aprovar", headers=self.admin_headers)
        self.assertEqual(approved.status_code, 200, approved.get_json())

        first_receipt = self.client.post(
            f"/compras/solicitacoes/{purchase['id']}/recebimentos",
            headers=self.gestor_headers,
            json={"quantity": 2, "idempotency_key": "rcv-purchase-001"},
        )
        self.assertEqual(first_receipt.status_code, 200, first_receipt.get_json())
        self.assertEqual(first_receipt.get_json()["data"]["status"], "PARCIALMENTE_RECEBIDA")

        duplicate = self.client.post(
            f"/compras/solicitacoes/{purchase['id']}/recebimentos",
            headers=self.gestor_headers,
            json={"quantity": 2, "idempotency_key": "rcv-purchase-001"},
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        self.assertEqual(duplicate.get_json()["data"]["received_quantity"], 2)

        final_receipt = self.client.post(
            f"/compras/solicitacoes/{purchase['id']}/recebimentos",
            headers=self.gestor_headers,
            json={
                "quantity": 3,
                "idempotency_key": "rcv-purchase-002",
                "invoice_number": "NF-2026-002",
                "invoice_series": "3",
                "invoice_date": date.today().isoformat(),
                "invoice_value": "18450.75",
                "invoice_file_path": "/uploads/compras/nf-2026-002.pdf",
            },
        )
        self.assertEqual(final_receipt.status_code, 200, final_receipt.get_json())
        self.assertEqual(final_receipt.get_json()["data"]["status"], "RECEBIDA")
        detail = self.client.get(f"/compras/solicitacoes/{purchase['id']}", headers=self.gestor_headers)
        self.assertEqual(detail.status_code, 200, detail.get_json())
        detail_data = detail.get_json()["data"]
        self.assertEqual(detail_data["remaining_quantity"], 0)
        self.assertEqual(len(detail_data["receipts"]), 2)
        invoice = next(receipt for receipt in detail_data["receipts"] if receipt["invoice_number"])
        self.assertEqual(invoice["invoice_number"], "NF-2026-002")
        self.assertEqual(invoice["invoice_series"], "3")
        self.assertEqual(invoice["invoice_value"], 18450.75)
        self.assertEqual(invoice["invoice_file_path"], "/uploads/compras/nf-2026-002.pdf")
        self.assertEqual(detail_data["created_by"]["login"], "gestor_compras")
        with self.app.app_context():
            self.assertEqual(db.session.get(Material, self.material_id).quantidade_estoque, 5)

    def test_purchase_import_controls_are_admin_only(self):
        denied = self.client.get("/compras/importacoes", headers=self.gestor_headers)
        self.assertEqual(denied.status_code, 403, denied.get_json())

        denied_upload = self.client.post("/compras/importacoes", headers=self.gestor_headers)
        self.assertEqual(denied_upload.status_code, 403, denied_upload.get_json())

        allowed = self.client.get("/compras/importacoes", headers=self.admin_headers)
        self.assertEqual(allowed.status_code, 200, allowed.get_json())

    def test_purchase_invoice_is_linked_to_pc_and_received_by_item(self):
        with self.app.app_context():
            material = Material(referencia="MAT-NF-30001", descricao="Material NF 30001", aplicacao_tipo="ambos", quantidade_estoque=0, estoque_minimo=1)
            db.session.add(material)
            db.session.commit()
            material_id = material.id
        request = self.client.post(
            "/compras/solicitacoes",
            headers=self.gestor_headers,
            json={"items": [{"item_type": "MATERIAL", "material_id": material_id, "quantity": 5}]},
        )
        self.assertEqual(request.status_code, 201, request.get_json())
        purchase = request.get_json()["data"]
        approved = self.client.post(f"/compras/solicitacoes/{purchase['id']}/aprovar", headers=self.admin_headers)
        self.assertEqual(approved.status_code, 200, approved.get_json())

        order = self.client.post(
            "/compras/pedidos",
            headers=self.gestor_headers,
            json={
                "pc_number": "PC-NF-30001",
                "supplier_raw": "Provedor NF 30001",
                "items": [{"purchase_request_item_id": purchase["items"][0]["id"], "quantity_ordered": 5}],
            },
        )
        self.assertEqual(order.status_code, 201, order.get_json())
        order_item_id = order.get_json()["data"]["purchase_order"]["items"][0]["id"]

        invoice = self.client.post(
            "/compras/notas",
            headers=self.gestor_headers,
            json={
                "purchase_order_id": order.get_json()["data"]["purchase_order"]["id"],
                "invoice_number": "NF-30001",
                "series": "1",
                "invoice_date": date.today().isoformat(),
                "invoice_value": "1250.00",
                "file_path": "/uploads/compras/nf-30001.pdf",
                "items": [{"purchase_order_item_id": order_item_id, "quantity_invoiced": 5}],
            },
        )
        self.assertEqual(invoice.status_code, 201, invoice.get_json())
        invoice_data = invoice.get_json()["data"]["invoice"]
        self.assertEqual(invoice_data["invoice_number"], "NF-30001")
        self.assertEqual(invoice_data["file_path"], "/uploads/compras/nf-30001.pdf")
        invoice_item_id = invoice_data["items"][0]["id"]

        pending = self.client.get("/compras/notas/pendentes", headers=self.gestor_headers)
        self.assertEqual(pending.status_code, 200, pending.get_json())
        pending_data = pending.get_json()["data"]
        self.assertFalse(any(row["purchase_order_id"] == invoice_data["purchase_orders"][0]["id"] for row in pending_data["pending_nf"]))
        self.assertEqual(pending_data["pending_receipts"][0]["invoice_number"], "NF-30001")
        self.assertEqual(pending_data["pending_receipts"][0]["remaining_receipt_quantity"], 5.0)

        paged_pending = self.client.get("/compras/notas/pendentes?page=1&per_page=100", headers=self.gestor_headers)
        self.assertEqual(paged_pending.status_code, 200, paged_pending.get_json())
        self.assertEqual(paged_pending.get_json()["data"]["pagination"]["per_page"], 100)

        filtered_pending = self.client.get(
            "/compras/notas/pendentes?page=1&per_page=100&q=NF-30001&status=AGUARDANDO_RECEBIMENTO",
            headers=self.gestor_headers,
        )
        self.assertEqual(filtered_pending.status_code, 200, filtered_pending.get_json())
        filtered_pending_data = filtered_pending.get_json()["data"]
        self.assertEqual(filtered_pending_data["pagination"]["pending_nf"]["total"], 0)
        self.assertEqual(filtered_pending_data["pagination"]["pending_receipts"]["total"], 1)

        first_receipt = self.client.post(
            "/compras/notas/{}/recebimentos".format(invoice_data["id"]),
            headers=self.gestor_headers,
            json={"invoice_item_id": invoice_item_id, "quantity_received": 3, "idempotency_key": "nf-30001-recv-001"},
        )
        self.assertEqual(first_receipt.status_code, 200, first_receipt.get_json())
        self.assertEqual(first_receipt.get_json()["data"]["invoice"]["status"], "RECEBIMENTO_PARCIAL")

        final_receipt = self.client.post(
            "/compras/notas/{}/recebimentos".format(invoice_data["id"]),
            headers=self.gestor_headers,
            json={"invoice_item_id": invoice_item_id, "quantity_received": 2, "idempotency_key": "nf-30001-recv-002"},
        )
        self.assertEqual(final_receipt.status_code, 200, final_receipt.get_json())
        self.assertEqual(final_receipt.get_json()["data"]["invoice"]["status"], "RECEBIDA")
        self.assertEqual(final_receipt.get_json()["data"]["purchase_request"]["status"], "RECEBIDA")

        paged_orders = self.client.get("/compras/pedidos?page=1&per_page=100&q=PC-NF-30001", headers=self.gestor_headers)
        self.assertEqual(paged_orders.status_code, 200, paged_orders.get_json())
        paged_data = paged_orders.get_json()["data"]
        self.assertEqual(paged_data["pagination"]["page"], 1)
        self.assertEqual(paged_data["pagination"]["total"], 1)
        self.assertEqual(paged_data["items"][0]["pc_number"], "PC-NF-30001")

        history = self.client.get(
            "/compras/pedidos/{}/historico".format(order.get_json()["data"]["purchase_order"]["id"]),
            headers=self.gestor_headers,
        )
        self.assertEqual(history.status_code, 200, history.get_json())
        history_data = history.get_json()["data"]
        self.assertEqual(history_data["order"]["pc_number"], "PC-NF-30001")
        self.assertEqual(history_data["items"][0]["sc_number"], purchase["sc_number"])
        self.assertEqual(history_data["items"][0]["invoices"][0]["number"], "NF-30001")
        self.assertEqual(history_data["items"][0]["quantity_received"], 5.0)

        with self.app.app_context():
            self.assertEqual(db.session.get(Material, material_id).quantidade_estoque, 5)

    def test_purchase_process_center_filters_and_summary(self):
        response = self.client.post(
            "/compras/solicitacoes",
            headers=self.gestor_headers,
            json={
                "sc_date": date.today().isoformat(),
                "module": "LBS",
                "equipment_raw": "LBS-04",
                "items": [{"item_type": "SERVICO", "description_raw": "Inspeção elétrica", "quantity": 1}],
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        purchase = response.get_json()["data"]

        center = self.client.get("/compras/central-processos?item_type=SERVICO&q=LBS-04&page=1&per_page=100", headers=self.gestor_headers)
        self.assertEqual(center.status_code, 200, center.get_json())
        data = center.get_json()["data"]
        self.assertEqual(data["summary"]["items"], 1)
        self.assertEqual(data["summary"]["total_items"], 1)
        self.assertEqual(data["summary"]["page"], 1)
        self.assertEqual(data["summary"]["per_page"], 100)
        self.assertEqual(data["summary"]["total_pages"], 1)
        self.assertLessEqual(len(data["items"]), 100)
        self.assertEqual(data["summary"]["pending_pc"], 1)
        self.assertEqual(data["items"][0]["purchase_request_id"], purchase["id"])
        self.assertEqual(data["items"][0]["item_status"], "AGUARDANDO_PC")
        self.assertEqual(data["items"][0]["next_action"], "EMITIR_PC")
        self.assertIsNotNone(data["items"][0]["updated_at"])

        paged_requests = self.client.get("/compras/solicitacoes?modo=OPERACIONAL&page=1&per_page=100", headers=self.gestor_headers)
        self.assertEqual(paged_requests.status_code, 200, paged_requests.get_json())
        paged_request_data = paged_requests.get_json()["data"]
        self.assertLessEqual(len(paged_request_data["items"]), 100)
        self.assertEqual(paged_request_data["pagination"]["per_page"], 100)

        indicators = self.client.get("/compras/indicadores", headers=self.gestor_headers)
        self.assertEqual(indicators.status_code, 200, indicators.get_json())
        indicator_data = indicators.get_json()["data"]
        self.assertGreaterEqual(indicator_data["open_requests"], 1)
        self.assertGreaterEqual(indicator_data["pending_pc_items"], 1)
        self.assertIn("pending_nf_items", indicator_data)

        report = self.client.get("/compras/relatorios/resumo", headers=self.gestor_headers)
        self.assertEqual(report.status_code, 200, report.get_json())
        report_data = report.get_json()["data"]
        self.assertGreaterEqual(report_data["summary"]["items"], 1)
        self.assertIn("SERVICO", report_data["by_type"])

        invalid_period = self.client.get(
            "/compras/central-processos?date_from=2026-08-20&date_to=2026-08-01",
            headers=self.gestor_headers,
        )
        self.assertEqual(invalid_period.status_code, 400, invalid_period.get_json())

    def test_purchase_report_exports_and_schedule_controls(self):
        pdf = self.client.get("/compras/relatorios/exportar?formato=PDF", headers=self.gestor_headers)
        self.assertEqual(pdf.status_code, 200)
        self.assertIn("application/pdf", pdf.content_type)

        xlsx = self.client.get("/compras/relatorios/exportar?formato=XLSX", headers=self.gestor_headers)
        self.assertEqual(xlsx.status_code, 200)
        self.assertIn("spreadsheetml", xlsx.content_type)

        denied = self.client.get("/compras/relatorios/automaticos", headers=self.gestor_headers)
        self.assertEqual(denied.status_code, 403, denied.get_json())
        created = self.client.post(
            "/compras/relatorios/automaticos",
            headers=self.admin_headers,
            json={"name": "Compras semanal", "frequency": "WEEKLY", "period_days": 7, "export_format": "XLSX", "next_run_at": "2000-01-01T00:00:00"},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        schedule_id = created.get_json()["data"]["id"]
        executed = self.client.post(f"/compras/relatorios/automaticos/executar?schedule_id={schedule_id}", headers=self.admin_headers)
        self.assertEqual(executed.status_code, 200, executed.get_json())
        run = executed.get_json()["data"]["runs"][0]
        self.assertEqual(run["status"], "CONCLUIDO")
        downloaded = self.client.get(f"/compras/relatorios/automaticos/runs/{run['id']}/download", headers=self.gestor_headers)
        self.assertEqual(downloaded.status_code, 200)
        downloaded.close()
        Path(run["file_path"]).unlink(missing_ok=True)

    def test_purchase_request_supports_multiple_material_and_service_items(self):
        response = self.client.post(
            "/compras/solicitacoes",
            headers=self.gestor_headers,
            json={
                "sc_date": date.today().isoformat(),
                "external_quote_number": "ORC-2026-001",
                "requester_raw": "Equipe de Manutenção",
                "cost_center": "Manutenção de Máquinas Pesadas",
                "module": "RTG",
                "equipment_raw": "RTG-01",
                "work_order_number": "OS-7788",
                "priority": "ALTA",
                "items": [
                    {"item_type": "MATERIAL", "material_id": self.material_id, "quantity": 4, "unit_of_measure": "UN"},
                    {"item_type": "SERVICO", "service_catalog_id": self.service_id, "quantity": 1, "unit_of_measure": "SV"},
                ],
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        data = response.get_json()["data"]
        self.assertEqual(data["request_type"], "MISTO")
        self.assertEqual(data["item_count"], 2)
        self.assertEqual(data["requested_quantity"], 5)
        self.assertEqual(data["sc_number"], data["code"])
        self.assertEqual(data["module"], "RTG")
        self.assertEqual([item["status"] for item in data["items"]], ["AGUARDANDO_PC", "AGUARDANDO_PC"])
        self.assertEqual(data["items"][0]["product_code_raw"], "MAT-COMPRA")
        self.assertEqual(data["items"][1]["description_raw"], "Reparo de bomba hidráulica")

        denied_receive = self.client.post(
            f"/compras/solicitacoes/{data['id']}/recebimentos",
            headers=self.gestor_headers,
            json={"quantity": 1, "idempotency_key": "rcv-mixed-001"},
        )
        self.assertEqual(denied_receive.status_code, 400, denied_receive.get_json())

    def test_purchase_order_supports_partial_and_multiple_orders_for_same_sc(self):
        request = self.client.post(
            "/compras/solicitacoes",
            headers=self.gestor_headers,
            json={"items": [{"item_type": "MATERIAL", "material_id": self.material_id, "quantity": 5}]},
        )
        self.assertEqual(request.status_code, 201, request.get_json())
        purchase = request.get_json()["data"]
        approved = self.client.post(f"/compras/solicitacoes/{purchase['id']}/aprovar", headers=self.admin_headers)
        self.assertEqual(approved.status_code, 200, approved.get_json())
        item_id = purchase["items"][0]["id"]

        provider = self.client.post(
            "/compras/provedores",
            headers=self.admin_headers,
            json={"code": "PROV-PC-001", "name": "Provedor do PC"},
        )
        self.assertEqual(provider.status_code, 201, provider.get_json())
        provider_id = provider.get_json()["data"]["id"]

        first_pc = self.client.post(
            "/compras/pedidos",
            headers=self.gestor_headers,
            json={
                "pc_number": "PC-50001",
                "supplier_id": provider_id,
                "total_value": "200.00",
                "items": [{"purchase_request_item_id": item_id, "quantity_ordered": 2, "unit_price": "100.00"}],
            },
        )
        self.assertEqual(first_pc.status_code, 201, first_pc.get_json())
        first_data = first_pc.get_json()["data"]
        self.assertEqual(first_data["purchase_order"]["pc_number"], "PC-50001")

        pending = self.client.get("/compras/pedidos/pendentes", headers=self.gestor_headers)
        self.assertEqual(pending.status_code, 200, pending.get_json())
        pending_item = next(item for row in pending.get_json()["data"] for item in row["items"] if item["id"] == item_id)
        self.assertEqual(pending_item["quantity_ordered"], 2.0)
        self.assertEqual(pending_item["remaining_order_quantity"], 3.0)
        self.assertEqual(pending_item["status"], "PC_PARCIAL")

        second_pc = self.client.post(
            "/compras/pedidos",
            headers=self.gestor_headers,
            json={
                "pc_number": "PC-50002",
                "supplier_raw": "Outro Provedor",
                "items": [{"purchase_request_item_id": item_id, "quantity_ordered": 3}],
            },
        )
        self.assertEqual(second_pc.status_code, 201, second_pc.get_json())
        final_request = self.client.get(f"/compras/solicitacoes/{purchase['id']}", headers=self.gestor_headers)
        self.assertEqual(final_request.status_code, 200, final_request.get_json())
        self.assertEqual(final_request.get_json()["data"]["status"], "EM_TRANSITO")
        self.assertEqual(final_request.get_json()["data"]["pc_count"], 2)

        pending_after = self.client.get("/compras/pedidos/pendentes", headers=self.gestor_headers)
        self.assertEqual(pending_after.status_code, 200, pending_after.get_json())
        self.assertFalse(any(row["purchase_request_id"] == purchase["id"] for row in pending_after.get_json()["data"]))

    def test_provider_registration_is_admin_only_and_can_be_updated(self):
        denied_list = self.client.get("/compras/provedores", headers=self.gestor_headers)
        self.assertEqual(denied_list.status_code, 403, denied_list.get_json())
        denied_create = self.client.post(
            "/compras/provedores",
            headers=self.gestor_headers,
            json={"code": "PROV-NEGADO", "name": "Não deve cadastrar"},
        )
        self.assertEqual(denied_create.status_code, 403, denied_create.get_json())

        created = self.client.post(
            "/compras/provedores",
            headers=self.admin_headers,
            json={
                "code": "PROV-ADM",
                "name": "Provedor Administrativo",
                "legal_name": "Provedor Administrativo Ltda",
                "tax_id": "00.000.000/0001-00",
                "homologated": True,
                "preferred": True,
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        provider_id = created.get_json()["data"]["id"]
        updated = self.client.put(
            f"/compras/provedores/{provider_id}",
            headers=self.admin_headers,
            json={
                "code": "PROV-ADM",
                "name": "Provedor Administrativo Atualizado",
                "active": False,
                "homologated": True,
                "preferred": False,
            },
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["data"]["name"], "Provedor Administrativo Atualizado")
        self.assertFalse(updated.get_json()["data"]["active"])

        legacy_list = self.client.get("/compras/fornecedores", headers=self.admin_headers)
        self.assertEqual(legacy_list.status_code, 200, legacy_list.get_json())


if __name__ == "__main__":
    unittest.main()
